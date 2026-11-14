import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph

from paysentineliq.application.errors import (
    AnalysisTimeoutError,
    UnsupportedDocumentError,
)
from paysentineliq.application.ports.analysis import (
    AnalysisDocument,
    AnalysisEventPort,
    AnalysisRepositoryPort,
    document_type_for,
)
from paysentineliq.application.ports.guardrails import (
    GuardrailMetricsPort,
    InjectionClassifierPort,
    JudgeRequest,
    JudgeVerdict,
    ReportJudgePort,
)
from paysentineliq.application.ports.ingestion import DocumentIngestionPort
from paysentineliq.application.ports.interpretation import (
    EvidenceInterpreterPort,
    InterpretationEvidence,
    InterpretationRequest,
    InterpretationResult,
)
from paysentineliq.application.ports.rag import RagContextPort
from paysentineliq.application.ports.storage import StoragePort
from paysentineliq.application.queries.fraud_features import (
    summary_from_boleto,
    summary_from_payslip,
)
from paysentineliq.application.queries.fraud_scoring import (
    FraudScoringRequest,
    FraudScoringService,
)
from paysentineliq.application.queries.knowledge_retrieval import (
    KnowledgeQuery,
    RetrievedPassage,
)
from paysentineliq.application.security.guardrails import (
    GUARDRAIL_LAYER_CLASSIFIER,
    GUARDRAIL_LAYER_JUDGE,
    GUARDRAIL_LAYER_OUTPUT,
    GUARDRAIL_RULE_SET_VERSION,
    GuardrailFinding,
    InputGuardrailService,
    OutputGuardrailService,
    dedupe_findings,
    findings_to_evidence,
)
from paysentineliq.application.security.redaction import mask_pii, mask_terms
from paysentineliq.application.security.storage_keys import (
    build_analysis_report_key,
)
from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisEvent,
    AnalysisEventType,
    AnalysisEvidence,
    AnalysisReport,
    AnalysisStatus,
    DegradationFlag,
)
from paysentineliq.domain.boleto.analysis import BoletoAnalysis, analyze_boleto
from paysentineliq.domain.boleto.bank_directory import (
    BankDirectory,
    load_bank_directory,
)
from paysentineliq.domain.boleto.extraction import extract_boleto_fields
from paysentineliq.domain.ingestion import VisualSignal
from paysentineliq.domain.payslip.analysis import PayslipAnalysis, analyze_payslip
from paysentineliq.domain.payslip.extraction import extract_payslip_fields
from paysentineliq.domain.payslip.regulatory import (
    RegulatoryTables,
    load_regulatory_tables,
)
from paysentineliq.domain.payslip.rules import EvidenceStatus
from paysentineliq.domain.scoring import (
    DeterministicSummary,
    FraudScore,
    RiskBand,
    ScoringConfig,
    SeverityLevel,
)
from paysentineliq.infrastructure.ai.report import (
    boleto_evidence,
    boleto_fields,
    payslip_evidence,
    payslip_fields,
)
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.guardrails.training import (
    load_injection_classifier_or_none,
)
from paysentineliq.infrastructure.metrics.guardrails import InMemoryGuardrailMetrics


class AnalysisGraphState(TypedDict, total=False):
    analysis_id: UUID
    document: AnalysisDocument
    data: bytes
    locale: str
    ocr_text: str
    sanitized_text: str
    visual_signals: tuple[VisualSignal, ...]
    document_type: AnalysisDocumentType
    boleto_analysis: BoletoAnalysis | None
    payslip_analysis: PayslipAnalysis | None
    deterministic_summary: DeterministicSummary | None
    fraud_score: FraudScore | None
    rag_passages: tuple[RetrievedPassage, ...]
    interpretation: InterpretationResult | None
    guardrail_findings: tuple[GuardrailFinding, ...]
    guardrail_evidence: tuple[AnalysisEvidence, ...]
    input_guard_triggered: bool
    classifier_version: str | None
    judge_verdict: JudgeVerdict | None
    degradation_flags: tuple[DegradationFlag, ...]
    final_score: int
    final_band: RiskBand
    llm_adjustment: int
    justification: str
    inconsistencies: tuple[str, ...]
    report: AnalysisReport | None


class LangGraphAnalysisOrchestrator:
    def __init__(
        self,
        *,
        ingestion: DocumentIngestionPort,
        fraud_service: FraudScoringService,
        retriever: RagContextPort,
        interpreter: EvidenceInterpreterPort,
        analyses: AnalysisRepositoryPort,
        events: AnalysisEventPort,
        storage: StoragePort,
        settings: Settings,
        bank_directory: BankDirectory | None = None,
        regulatory: RegulatoryTables | None = None,
        clock: Callable[[], datetime] | None = None,
        scoring_config: ScoringConfig | None = None,
        judge: ReportJudgePort | None = None,
        classifier: InjectionClassifierPort | None = None,
        metrics: GuardrailMetricsPort | None = None,
    ) -> None:
        self._ingestion = ingestion
        self._fraud_service = fraud_service
        self._retriever = retriever
        self._interpreter = interpreter
        self._analyses = analyses
        self._events = events
        self._storage = storage
        self._settings = settings
        self._judge = judge
        self._judge_enabled = settings.guardrail_judge_enabled
        self._classifier_enabled = settings.guardrail_classifier_enabled
        if classifier is None and settings.guardrail_classifier_enabled:
            classifier = load_injection_classifier_or_none(
                Path(settings.guardrail_classifier_model_dir),
            )
        self._input_classifier = classifier
        self._metrics = metrics if metrics is not None else InMemoryGuardrailMetrics()
        self._input_guard = InputGuardrailService(
            max_chars=settings.guardrail_max_text_chars,
            classifier=classifier,
            threshold=settings.guardrail_classifier_threshold,
        )
        self._output_guard = OutputGuardrailService(
            allowed_urls=frozenset(settings.guardrail_allowed_output_urls_list),
        )
        self._bank_directory = (
            bank_directory if bank_directory is not None else load_bank_directory()
        )
        self._regulatory = regulatory if regulatory is not None else load_regulatory_tables()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._scoring_config = scoring_config if scoring_config is not None else ScoringConfig()
        self._node_timeout = settings.ai_node_timeout_seconds
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(AnalysisGraphState)
        graph.add_node("load", self._load_node)
        graph.add_node("ingest", self._ingest_node)
        graph.add_node("guard", self._guard_node)
        graph.add_node("classify", self._classify_node)
        graph.add_node("boleto", self._boleto_node)
        graph.add_node("payslip", self._payslip_node)
        graph.add_node("fraud", self._fraud_node)
        graph.add_node("rag", self._rag_node)
        graph.add_node("interpret", self._interpret_node)
        graph.add_node("persist", self._persist_node)
        graph.set_entry_point("load")
        graph.add_edge("load", "ingest")
        graph.add_edge("ingest", "guard")
        graph.add_edge("guard", "classify")
        graph.add_conditional_edges(
            "classify",
            self._route_document,
            {"boleto": "boleto", "payslip": "payslip"},
        )
        graph.add_edge("boleto", "fraud")
        graph.add_edge("payslip", "fraud")
        graph.add_edge("fraud", "rag")
        graph.add_edge("rag", "interpret")
        graph.add_edge("interpret", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    async def run(
        self,
        *,
        analysis_id: UUID,
        document: AnalysisDocument,
        data: bytes,
        locale: str = "pt",
    ) -> AnalysisReport:
        initial: AnalysisGraphState = {
            "analysis_id": analysis_id,
            "document": document,
            "data": data,
            "locale": locale,
            "degradation_flags": (),
            "guardrail_findings": (),
            "guardrail_evidence": (),
            "input_guard_triggered": False,
        }
        result: Any = await self._graph.ainvoke(initial)
        report = result.get("report") if isinstance(result, dict) else None
        if not isinstance(report, AnalysisReport):
            raise RuntimeError("analysis did not produce a report")
        return report

    async def _load_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        document = state["document"]
        flags = self._flags(state)
        await self._processing(
            state["analysis_id"],
            "load",
            {
                "node": "load",
                "document_id": str(document.id),
                "kind": document.kind.value,
            },
            flags,
        )
        return {}

    async def _ingest_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        flags = self._flags(state)
        try:
            result = await asyncio.wait_for(
                self._ingestion.ingest(state["data"]),
                timeout=self._node_timeout,
            )
        except TimeoutError as exc:
            raise AnalysisTimeoutError("ingest") from exc
        text = "\n".join(block.text for block in result.blocks)
        await self._processing(
            state["analysis_id"],
            "ingest",
            {
                "node": "ingest",
                "pages": str(result.page_count),
                "signals": str(len(result.signals)),
            },
            flags,
        )
        return {
            "ocr_text": text,
            "visual_signals": result.signals,
        }

    async def _guard_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        result = self._input_guard.inspect(state["ocr_text"])
        flags = self._flags(state)
        classifier_unavailable = result.classifier_unavailable or (
            self._classifier_enabled and self._input_classifier is None
        )
        if classifier_unavailable:
            flags = self._add_flag(
                flags,
                DegradationFlag.GUARDRAIL_CLASSIFIER_UNAVAILABLE,
            )
            await self._append_degraded(
                state["analysis_id"],
                DegradationFlag.GUARDRAIL_CLASSIFIER_UNAVAILABLE,
                "guard",
            )
            self._metrics.record(GUARDRAIL_LAYER_CLASSIFIER, "unavailable")
        if result.triggered:
            flags = self._add_flag(flags, DegradationFlag.PROMPT_INJECTION_DETECTED)
        await self._append_guardrail_findings(
            state["analysis_id"],
            result.findings,
        )
        await self._processing(
            state["analysis_id"],
            "guard",
            {
                "node": "guard",
                "findings": str(len(result.findings)),
                "triggered": "1" if result.triggered else "0",
                "sanitized": "1",
            },
            flags,
        )
        return {
            "sanitized_text": result.sanitized.text,
            "guardrail_findings": result.findings,
            "guardrail_evidence": findings_to_evidence(result.findings),
            "input_guard_triggered": result.triggered,
            "classifier_version": result.classifier_version,
            "degradation_flags": flags,
        }

    async def _classify_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        document = state["document"]
        document_type = document_type_for(document.kind)
        if document_type is None:
            raise UnsupportedDocumentError()
        flags = self._flags(state)
        await self._processing(
            state["analysis_id"],
            "classify",
            {"node": "classify", "document_type": document_type.value},
            flags,
        )
        return {"document_type": document_type}

    def _route_document(self, state: AnalysisGraphState) -> str:
        document_type = state.get("document_type")
        if document_type is None:
            raise UnsupportedDocumentError()
        return document_type.value

    async def _boleto_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        flags = self._flags(state)
        try:
            analysis, summary = await asyncio.wait_for(
                asyncio.to_thread(self._run_boleto, state["ocr_text"]),
                timeout=self._node_timeout,
            )
        except TimeoutError as exc:
            raise AnalysisTimeoutError("boleto") from exc
        await self._append_rule_events(
            state["analysis_id"],
            analysis.evidence,
            analysis.rule_set_version,
        )
        await self._processing(
            state["analysis_id"],
            "boleto",
            {
                "node": "boleto",
                "subscore": str(analysis.subscore),
                "evidence": str(len(analysis.evidence)),
            },
            flags,
        )
        return {
            "boleto_analysis": analysis,
            "deterministic_summary": summary,
        }

    async def _payslip_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        flags = self._flags(state)
        try:
            analysis, summary = await asyncio.wait_for(
                asyncio.to_thread(self._run_payslip, state["ocr_text"]),
                timeout=self._node_timeout,
            )
        except TimeoutError as exc:
            raise AnalysisTimeoutError("payslip") from exc
        await self._append_rule_events(
            state["analysis_id"],
            analysis.evidence,
            analysis.rule_set_version,
            only_triggered=True,
        )
        await self._processing(
            state["analysis_id"],
            "payslip",
            {
                "node": "payslip",
                "subscore": str(analysis.subscore),
                "evidence": str(len(analysis.evidence)),
            },
            flags,
        )
        return {
            "payslip_analysis": analysis,
            "deterministic_summary": summary,
        }

    async def _fraud_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        summary = state.get("deterministic_summary")
        if summary is None:
            raise RuntimeError("deterministic summary is missing")
        flags = self._flags(state)
        try:
            score = await asyncio.wait_for(
                asyncio.to_thread(
                    self._fraud_service.score,
                    FraudScoringRequest(
                        deterministic=summary,
                        visual_signals=state.get("visual_signals", ()),
                    ),
                ),
                timeout=self._node_timeout,
            )
        except TimeoutError as exc:
            raise AnalysisTimeoutError("fraud") from exc
        if score.ml_unavailable and DegradationFlag.ML_UNAVAILABLE not in flags:
            flags = (*flags, DegradationFlag.ML_UNAVAILABLE)
            await self._append_degraded(
                state["analysis_id"],
                DegradationFlag.ML_UNAVAILABLE,
                "fraud",
            )
        await self._processing(
            state["analysis_id"],
            "fraud",
            {
                "node": "fraud",
                "base_score": str(score.score),
                "ml_available": "0" if score.ml_unavailable else "1",
            },
            flags,
        )
        return {"fraud_score": score, "degradation_flags": flags}

    async def _rag_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        flags = self._flags(state)
        try:
            result = await asyncio.wait_for(
                self._retriever.retrieve(
                    KnowledgeQuery(
                        text=self._rag_query(state),
                        as_of=self._clock().date(),
                        limit=5,
                    ),
                ),
                timeout=self._node_timeout,
            )
        except Exception:
            flags = self._add_flag(flags, DegradationFlag.RAG_UNAVAILABLE)
            await self._append_degraded(
                state["analysis_id"],
                DegradationFlag.RAG_UNAVAILABLE,
                "rag",
            )
            await self._processing(
                state["analysis_id"],
                "rag",
                {"node": "rag", "passages": "0"},
                flags,
            )
            return {"rag_passages": (), "degradation_flags": flags}
        if result.rag_unavailable:
            flags = self._add_flag(flags, DegradationFlag.RAG_UNAVAILABLE)
            await self._append_degraded(
                state["analysis_id"],
                DegradationFlag.RAG_UNAVAILABLE,
                "rag",
            )
        await self._processing(
            state["analysis_id"],
            "rag",
            {"node": "rag", "passages": str(len(result.passages))},
            flags,
        )
        return {"rag_passages": result.passages, "degradation_flags": flags}

    async def _interpret_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        score = state.get("fraud_score")
        summary = state.get("deterministic_summary")
        if score is None or summary is None:
            raise RuntimeError("fraud score is missing")
        flags = self._flags(state)
        guardrail_evidence = tuple(state.get("guardrail_evidence", ()))
        interpretation: InterpretationResult | None = None
        rejection: str | None = None
        judge_verdict: JudgeVerdict | None = None

        if state.get("input_guard_triggered", False):
            rejection = "input"
        else:
            request = self._interpretation_request(state, score, flags)
            try:
                interpretation = await asyncio.wait_for(
                    self._interpreter.interpret(request),
                    timeout=self._node_timeout,
                )
            except Exception:
                flags = self._add_flag(flags, DegradationFlag.LLM_UNAVAILABLE)
                await self._append_degraded(
                    state["analysis_id"],
                    DegradationFlag.LLM_UNAVAILABLE,
                    "interpret",
                )
            if interpretation is not None:
                scanned, blocked, scan_findings = self._scan_interpretation(
                    state,
                    interpretation,
                )
                if scan_findings:
                    guardrail_evidence = self._merge_guardrail_evidence(
                        guardrail_evidence,
                        scan_findings,
                    )
                    await self._append_guardrail_findings(
                        state["analysis_id"],
                        scan_findings,
                    )
                if blocked:
                    rejection = "output"
                    flags = self._add_flag(flags, DegradationFlag.LLM_OUTPUT_REJECTED)
                    self._metrics.record(
                        GUARDRAIL_LAYER_OUTPUT,
                        "report_replaced_by_template",
                    )
                    interpretation = None
                else:
                    interpretation = scanned

        adjustment = self._adjustment(interpretation)
        candidate_score, candidate_band = self._score_with_adjustment(
            score,
            summary,
            adjustment,
        )
        if interpretation is not None and self._judge_enabled:
            judge_verdict, flags, guardrail_evidence, accepted = await self._judge_report(
                state,
                candidate_score,
                candidate_band,
                interpretation,
                flags,
                guardrail_evidence,
            )
            if not accepted:
                rejection = "judge"
                interpretation = None

        adjustment = self._adjustment(interpretation)
        final_score, band = self._score_with_adjustment(score, summary, adjustment)
        evidence_count = len(self._evidence_for(state)) + len(guardrail_evidence)
        if interpretation is not None:
            justification = interpretation.justification
            inconsistencies = interpretation.inconsistencies
        elif rejection is not None:
            justification = self._guarded_justification(
                state.get("locale", "pt"),
                final_score,
                band,
                evidence_count,
                rejection,
            )
            inconsistencies = ()
        else:
            justification = self._fallback_justification(
                state.get("locale", "pt"),
                final_score,
                band,
                evidence_count,
            )
            inconsistencies = ()
        await self._processing(
            state["analysis_id"],
            "interpret",
            {
                "node": "interpret",
                "llm_available": "0" if interpretation is None else "1",
                "adjustment": str(adjustment),
                "final_score": str(final_score),
                "guardrail_evidence": str(len(guardrail_evidence)),
                "guardrail_rejection": rejection or "",
            },
            flags,
        )
        return {
            "interpretation": interpretation,
            "judge_verdict": judge_verdict,
            "guardrail_evidence": guardrail_evidence,
            "llm_adjustment": adjustment,
            "final_score": final_score,
            "final_band": band,
            "justification": justification,
            "inconsistencies": inconsistencies,
            "degradation_flags": flags,
        }

    def _scan_interpretation(
        self,
        state: AnalysisGraphState,
        interpretation: InterpretationResult,
    ) -> tuple[InterpretationResult, bool, tuple[GuardrailFinding, ...]]:
        terms = self._sensitive_terms(state)
        justification_scan = self._output_guard.inspect(
            interpretation.justification,
            sensitive_terms=terms,
        )
        findings: list[GuardrailFinding] = list(justification_scan.findings)
        blocked = justification_scan.blocked
        inconsistencies: list[str] = []
        for item in interpretation.inconsistencies:
            scan = self._output_guard.inspect(item, sensitive_terms=terms)
            findings.extend(scan.findings)
            blocked = blocked or scan.blocked
            inconsistencies.append(scan.text)
        return (
            InterpretationResult(
                justification=justification_scan.text,
                inconsistencies=tuple(inconsistencies),
                model_version=interpretation.model_version,
                prompt_version=interpretation.prompt_version,
            ),
            blocked,
            tuple(findings),
        )

    async def _judge_report(
        self,
        state: AnalysisGraphState,
        candidate_score: int,
        candidate_band: RiskBand,
        interpretation: InterpretationResult,
        flags: tuple[DegradationFlag, ...],
        evidence: tuple[AnalysisEvidence, ...],
    ) -> tuple[
        JudgeVerdict | None, tuple[DegradationFlag, ...], tuple[AnalysisEvidence, ...], bool
    ]:
        if self._judge is None:
            flags = self._add_flag(flags, DegradationFlag.LLM_JUDGE_UNAVAILABLE)
            await self._append_degraded(
                state["analysis_id"],
                DegradationFlag.LLM_JUDGE_UNAVAILABLE,
                "interpret",
            )
            self._metrics.record(GUARDRAIL_LAYER_JUDGE, "unavailable")
            return None, flags, evidence, True
        request = JudgeRequest(
            document_type=state["document_type"].value,
            score=candidate_score,
            band=candidate_band.value,
            justification=interpretation.justification,
            inconsistencies=interpretation.inconsistencies,
            evidence=self._judge_evidence(state, evidence),
            language=state.get("locale", "pt"),
        )
        try:
            verdict = await asyncio.wait_for(
                self._judge.judge(request),
                timeout=self._node_timeout,
            )
        except Exception:
            flags = self._add_flag(flags, DegradationFlag.LLM_JUDGE_UNAVAILABLE)
            await self._append_degraded(
                state["analysis_id"],
                DegradationFlag.LLM_JUDGE_UNAVAILABLE,
                "interpret",
            )
            self._metrics.record(GUARDRAIL_LAYER_JUDGE, "unavailable")
            return None, flags, evidence, True
        self._metrics.record(
            GUARDRAIL_LAYER_JUDGE,
            "approved" if verdict.approved else "rejected",
        )
        if verdict.approved:
            return verdict, flags, evidence, True
        finding = GuardrailFinding(
            layer=GUARDRAIL_LAYER_JUDGE,
            code="judge_rejected",
            severity=SeverityLevel.HIGH,
            rule_id="guardrail.judge_rejected",
            message_key="guardrail.judge_rejected",
        )
        flags = self._add_flag(flags, DegradationFlag.LLM_JUDGE_REJECTED)
        evidence = self._merge_guardrail_evidence(evidence, (finding,))
        await self._append_guardrail_findings(state["analysis_id"], (finding,))
        return verdict, flags, evidence, False

    def _adjustment(self, interpretation: InterpretationResult | None) -> int:
        if interpretation is None:
            return 0
        return min(
            2 * len(interpretation.inconsistencies),
            self._settings.llm_max_score_adjustment,
        )

    def _score_with_adjustment(
        self,
        score: FraudScore,
        summary: DeterministicSummary,
        adjustment: int,
    ) -> tuple[int, RiskBand]:
        final_score = min(100, score.score + adjustment)
        if summary.critical_present:
            final_score = max(final_score, self._scoring_config.critical_floor)
        return final_score, self._band(final_score)

    def _judge_evidence(
        self,
        state: AnalysisGraphState,
        guardrail_evidence: tuple[AnalysisEvidence, ...],
    ) -> tuple[InterpretationEvidence, ...]:
        items = list(self._evidence_for(state))
        items.extend(
            InterpretationEvidence(
                rule_id=item.rule_id,
                severity=item.severity,
                weight=item.weight,
                message_key=item.message_key,
            )
            for item in guardrail_evidence
        )
        return tuple(items)

    @staticmethod
    def _merge_guardrail_evidence(
        existing: tuple[AnalysisEvidence, ...],
        findings: tuple[GuardrailFinding, ...],
    ) -> tuple[AnalysisEvidence, ...]:
        merged = list(existing)
        seen = {item.rule_id for item in merged}
        for item in findings_to_evidence(findings):
            if item.rule_id in seen:
                continue
            seen.add(item.rule_id)
            merged.append(item)
        return tuple(merged[:12])

    def _sensitive_terms(self, state: AnalysisGraphState) -> tuple[str, ...]:
        terms: list[str] = []
        boleto = state.get("boleto_analysis")
        if boleto is not None:
            fields = boleto.fields
            for text_field in (fields.beneficiary, fields.payer):
                if text_field is not None:
                    terms.append(text_field.value)
            for tax_field in (fields.beneficiary_tax_id, fields.payer_tax_id):
                if tax_field is not None:
                    terms.append(tax_field.value.digits)
            terms.extend(tax_item.value.digits for tax_item in fields.additional_tax_ids)
        payslip = state.get("payslip_analysis")
        if payslip is not None and payslip.payslip is not None:
            data = payslip.payslip
            for name in (data.employer_name, data.employee_name, data.employee_cpf_masked):
                if name:
                    terms.append(name)
            if data.employer_cnpj is not None:
                terms.append(data.employer_cnpj.digits)
        unique = {term.strip() for term in terms if len(term.strip()) >= 4}
        return tuple(sorted(unique))

    def _document_excerpt(self, state: AnalysisGraphState) -> str:
        text = state.get("sanitized_text", "")
        masked = mask_terms(mask_pii(text), self._sensitive_terms(state))
        return masked[: self._settings.guardrail_llm_excerpt_chars]

    async def _persist_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        boleto = state.get("boleto_analysis")
        payslip = state.get("payslip_analysis")
        fraud = state.get("fraud_score")
        if boleto is None and payslip is None:
            raise RuntimeError("analysis result is missing")
        if fraud is None:
            raise RuntimeError("fraud score is missing")
        analysis_id = state["analysis_id"]
        document = state["document"]
        flags = self._flags(state)
        interpretation = state.get("interpretation")
        if boleto is not None:
            fields = boleto_fields(boleto)
            evidence = boleto_evidence(boleto)
            rule_set_version = boleto.rule_set_version
            document_type = AnalysisDocumentType.BOLETO
        else:
            if payslip is None:
                raise RuntimeError("payslip analysis is missing")
            fields = payslip_fields(payslip)
            evidence = payslip_evidence(payslip)
            rule_set_version = payslip.rule_set_version
            document_type = AnalysisDocumentType.PAYSLIP
        guardrail_evidence = tuple(state.get("guardrail_evidence", ()))
        evidence = (*guardrail_evidence, *evidence)
        model_versions: dict[str, str] = {"guardrails": GUARDRAIL_RULE_SET_VERSION}
        if fraud.model_version is not None:
            model_versions["ml"] = fraud.model_version
        if interpretation is not None:
            model_versions["llm"] = interpretation.model_version
            model_versions["prompt"] = interpretation.prompt_version
        classifier_version = state.get("classifier_version")
        if classifier_version:
            model_versions["injection_classifier"] = classifier_version
        judge_verdict = state.get("judge_verdict")
        if judge_verdict is not None:
            model_versions["judge"] = judge_verdict.model_version
            model_versions["judge_prompt"] = judge_verdict.prompt_version
        report_key = build_analysis_report_key(
            owner_id=document.owner_id,
            analysis_id=analysis_id,
        )
        report = AnalysisReport(
            analysis_id=analysis_id,
            document_id=document.id,
            document_type=document_type,
            score=state["final_score"],
            band=state["final_band"],
            base_score=fraud.score,
            llm_adjustment=state["llm_adjustment"],
            fields=fields,
            evidence=evidence,
            justification=state["justification"],
            inconsistencies=state.get("inconsistencies", ()),
            rule_set_version=rule_set_version,
            model_versions=model_versions,
            degradation_flags=flags,
            report_s3_key=report_key,
            created_at=self._clock(),
        )
        payload = json.dumps(report.to_dict(), ensure_ascii=False).encode("utf-8")
        await self._storage.put(
            report_key,
            BytesIO(payload),
            content_type="application/json",
            size=len(payload),
            metadata={"analysis_id": str(analysis_id)},
        )
        await self._analyses.complete(
            analysis_id,
            score=report.score,
            band=report.band,
            rule_set_version=rule_set_version,
            model_versions=model_versions,
            degradation_flags=flags,
            state={
                "node": "persist",
                "score": str(report.score),
                "band": report.band.value,
            },
            report_s3_key=report_key,
        )
        await self._events.append(
            AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.COMPLETED,
                rule_set_version=rule_set_version,
                model_version=fraud.model_version,
                degradation_flags=flags,
                payload=self._completed_payload(
                    state,
                    fraud,
                    interpretation,
                    rule_set_version,
                ),
            ),
        )
        return {"report": report}

    async def _processing(
        self,
        analysis_id: UUID,
        node: str,
        state: dict[str, str],
        flags: tuple[DegradationFlag, ...],
    ) -> None:
        await self._events.append(
            AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.PROCESSING,
                degradation_flags=flags,
                payload={"node": node},
            ),
        )
        await self._analyses.update_state(
            analysis_id,
            status=AnalysisStatus.PROCESSING,
            state=state,
            degradation_flags=flags,
        )

    async def _append_rule_events(
        self,
        analysis_id: UUID,
        evidence: tuple[Any, ...],
        rule_set_version: str,
        *,
        only_triggered: bool = False,
    ) -> None:
        for item in evidence:
            if only_triggered and item.status is not EvidenceStatus.TRIGGERED:
                continue
            await self._events.append(
                AnalysisEvent(
                    analysis_id=analysis_id,
                    event_type=AnalysisEventType.RULE_TRIGGERED,
                    rule_code=item.rule_id,
                    rule_set_version=rule_set_version,
                    payload={
                        "severity": item.severity.value,
                        "weight": str(item.weight),
                    },
                ),
            )

    async def _append_guardrail_findings(
        self,
        analysis_id: UUID,
        findings: tuple[GuardrailFinding, ...],
    ) -> None:
        for finding in dedupe_findings(list(findings)):
            self._metrics.record(finding.layer, finding.code)
            await self._events.append(
                AnalysisEvent(
                    analysis_id=analysis_id,
                    event_type=AnalysisEventType.GUARDRAIL_TRIGGERED,
                    rule_code=finding.rule_id,
                    rule_set_version=GUARDRAIL_RULE_SET_VERSION,
                    payload={
                        "layer": finding.layer,
                        "code": finding.code,
                        "severity": finding.severity.value,
                    },
                ),
            )

    async def _append_degraded(
        self,
        analysis_id: UUID,
        flag: DegradationFlag,
        node: str,
    ) -> None:
        await self._events.append(
            AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.DEGRADED,
                degradation_flags=(flag,),
                payload={"flag": flag.value, "node": node},
            ),
        )

    def _run_boleto(
        self,
        text: str,
    ) -> tuple[BoletoAnalysis, DeterministicSummary]:
        analysis = analyze_boleto(
            extract_boleto_fields(text, bank_directory=self._bank_directory),
            bank_directory=self._bank_directory,
        )
        return analysis, summary_from_boleto(analysis)

    def _run_payslip(
        self,
        text: str,
    ) -> tuple[PayslipAnalysis, DeterministicSummary]:
        analysis = analyze_payslip(
            extract_payslip_fields(text),
            regulatory=self._regulatory,
            reference_date=self._clock().date(),
        )
        return analysis, summary_from_payslip(analysis)

    def _document_type(self, document: AnalysisDocument) -> AnalysisDocumentType | None:
        if document.kind.value == "bank_slip":
            return AnalysisDocumentType.BOLETO
        if document.kind.value == "payslip":
            return AnalysisDocumentType.PAYSLIP
        return None

    def _rag_query(self, state: AnalysisGraphState) -> str:
        evidence = self._evidence_for(state)
        codes = " ".join(item.rule_id for item in evidence)
        return f"{state.get('document_type', AnalysisDocumentType.BOLETO).value} {codes}".strip()

    def _evidence_for(
        self,
        state: AnalysisGraphState,
    ) -> tuple[InterpretationEvidence, ...]:
        boleto = state.get("boleto_analysis")
        if boleto is not None:
            return tuple(
                InterpretationEvidence(
                    rule_id=item.rule_id,
                    severity=item.severity.value,
                    weight=item.weight,
                    message_key=item.message_key,
                )
                for item in boleto.evidence
            )
        payslip = state.get("payslip_analysis")
        if payslip is not None:
            return tuple(
                InterpretationEvidence(
                    rule_id=item.rule_id,
                    severity=item.severity.value,
                    weight=item.weight,
                    message_key=item.message_key,
                )
                for item in payslip.evidence
                if item.status is EvidenceStatus.TRIGGERED
            )
        return ()

    def _interpretation_request(
        self,
        state: AnalysisGraphState,
        score: FraudScore,
        flags: tuple[DegradationFlag, ...],
    ) -> InterpretationRequest:
        passages = state.get("rag_passages", ())
        return InterpretationRequest(
            document_type=state["document_type"].value,
            score=score.score,
            band=score.band.value,
            evidence=self._evidence_for(state),
            rag_snippets=tuple(passage.content for passage in passages[:5]),
            language=state.get("locale", "pt"),
            degradation_flags=tuple(flag.value for flag in flags),
            document_excerpt=self._document_excerpt(state),
        )

    def _completed_payload(
        self,
        state: AnalysisGraphState,
        fraud: FraudScore,
        interpretation: InterpretationResult | None,
        rule_set_version: str,
    ) -> dict[str, str]:
        return {
            "deterministic_score": str(fraud.deterministic_score),
            "ml_probability": "" if fraud.ml_probability is None else str(fraud.ml_probability),
            "anomaly_score": "" if fraud.anomaly_score is None else str(fraud.anomaly_score),
            "visual_score": str(fraud.visual_score),
            "ml_component": "" if fraud.ml_component is None else str(fraud.ml_component),
            "visual_component": str(fraud.visual_component),
            "base_score": str(fraud.score),
            "llm_adjustment": str(state["llm_adjustment"]),
            "score": str(state["final_score"]),
            "band": state["final_band"].value,
            "rule_set_version": rule_set_version,
            "ml_model_version": fraud.model_version or "",
            "llm_model_version": (
                interpretation.model_version if interpretation is not None else ""
            ),
            "prompt_version": (interpretation.prompt_version if interpretation is not None else ""),
            "guardrail_rules": ",".join(
                sorted(
                    {item.rule_id for item in state.get("guardrail_evidence", ())},
                ),
            ),
            "guardrail_count": str(len(state.get("guardrail_evidence", ()))),
            "degradation_flags": ",".join(flag.value for flag in self._flags(state)),
        }

    def _band(self, score: int) -> RiskBand:
        if score <= self._scoring_config.low_max:
            return RiskBand.LOW
        if score <= self._scoring_config.attention_max:
            return RiskBand.ATTENTION
        return RiskBand.HIGH

    @staticmethod
    def _guarded_justification(
        locale: str,
        score: int,
        band: RiskBand,
        evidence_count: int,
        reason: str,
    ) -> str:
        language = locale.lower().split("-", 1)[0]
        if language == "es":
            if reason == "input":
                return (
                    f"Analisis deterministico: score {score} ({band.value}). "
                    "El texto del documento intento instruir al sistema; la explicacion "
                    f"del LLM fue suprimida y se conservaron {evidence_count} evidencias."
                )
            if reason == "output":
                return (
                    f"Analisis deterministico: score {score} ({band.value}). La revision "
                    "de seguridad rechazo la explicacion del modelo por riesgo de filtracion; "
                    f"el informe se genero a partir de {evidence_count} evidencias."
                )
            return (
                f"Analisis deterministico: score {score} ({band.value}). La revision "
                "independiente rechazo la explicacion del modelo; el informe se genero "
                f"a partir de {evidence_count} evidencias."
            )
        if language == "en":
            if reason == "input":
                return (
                    f"Deterministic analysis: score {score} ({band.value}). The document "
                    "text tried to instruct the system; the LLM explanation was suppressed "
                    f"and {evidence_count} evidence items were kept."
                )
            if reason == "output":
                return (
                    f"Deterministic analysis: score {score} ({band.value}). The security "
                    "review rejected the model explanation due to leakage risk; the report "
                    f"was generated from {evidence_count} evidence items."
                )
            return (
                f"Deterministic analysis: score {score} ({band.value}). The independent "
                "review rejected the model explanation; the report was generated from "
                f"{evidence_count} evidence items."
            )
        if reason == "input":
            return (
                f"Analise deterministica: score {score} ({band.value}). O texto do documento "
                "tentou instruir o sistema; a explicacao do LLM foi suprimida e "
                f"{evidence_count} evidencias foram mantidas."
            )
        if reason == "output":
            return (
                f"Analise deterministica: score {score} ({band.value}). A revisao de seguranca "
                "rejeitou a explicacao do modelo por risco de vazamento; o relatorio foi "
                f"gerado a partir de {evidence_count} evidencias."
            )
        return (
            f"Analise deterministica: score {score} ({band.value}). A revisao independente "
            "reprovou a explicacao do modelo; o relatorio foi gerado a partir de "
            f"{evidence_count} evidencias."
        )

    @staticmethod
    def _fallback_justification(
        locale: str,
        score: int,
        band: RiskBand,
        evidence_count: int,
    ) -> str:
        language = locale.lower().split("-", 1)[0]
        if language == "es":
            return (
                f"Analisis concluido con score {score} ({band.value}) y "
                f"{evidence_count} evidencias. La explicacion del LLM no estaba disponible."
            )
        if language == "en":
            return (
                f"Analysis completed with score {score} ({band.value}) and "
                f"{evidence_count} evidence items. The LLM explanation was unavailable."
            )
        return (
            f"Analise concluida com score {score} ({band.value}) e "
            f"{evidence_count} evidencias. A explicacao do LLM nao estava disponivel."
        )

    @staticmethod
    def _flags(state: AnalysisGraphState) -> tuple[DegradationFlag, ...]:
        return state.get("degradation_flags", ())

    @staticmethod
    def _add_flag(
        flags: tuple[DegradationFlag, ...],
        flag: DegradationFlag,
    ) -> tuple[DegradationFlag, ...]:
        return flags if flag in flags else (*flags, flag)
