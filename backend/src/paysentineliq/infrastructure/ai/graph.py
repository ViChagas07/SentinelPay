import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from io import BytesIO
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
from paysentineliq.application.security.storage_keys import (
    build_analysis_report_key,
)
from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisEvent,
    AnalysisEventType,
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
)
from paysentineliq.infrastructure.ai.report import (
    boleto_evidence,
    boleto_fields,
    payslip_evidence,
    payslip_fields,
)
from paysentineliq.infrastructure.config import Settings


class AnalysisGraphState(TypedDict, total=False):
    analysis_id: UUID
    document: AnalysisDocument
    data: bytes
    locale: str
    ocr_text: str
    visual_signals: tuple[VisualSignal, ...]
    document_type: AnalysisDocumentType
    boleto_analysis: BoletoAnalysis | None
    payslip_analysis: PayslipAnalysis | None
    deterministic_summary: DeterministicSummary | None
    fraud_score: FraudScore | None
    rag_passages: tuple[RetrievedPassage, ...]
    interpretation: InterpretationResult | None
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
    ) -> None:
        self._ingestion = ingestion
        self._fraud_service = fraud_service
        self._retriever = retriever
        self._interpreter = interpreter
        self._analyses = analyses
        self._events = events
        self._storage = storage
        self._settings = settings
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
        graph.add_node("classify", self._classify_node)
        graph.add_node("boleto", self._boleto_node)
        graph.add_node("payslip", self._payslip_node)
        graph.add_node("fraud", self._fraud_node)
        graph.add_node("rag", self._rag_node)
        graph.add_node("interpret", self._interpret_node)
        graph.add_node("persist", self._persist_node)
        graph.set_entry_point("load")
        graph.add_edge("load", "ingest")
        graph.add_edge("ingest", "classify")
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
        request = self._interpretation_request(state, score, flags)
        interpretation: InterpretationResult | None
        try:
            interpretation = await asyncio.wait_for(
                self._interpreter.interpret(request),
                timeout=self._node_timeout,
            )
        except Exception:
            interpretation = None
            flags = self._add_flag(flags, DegradationFlag.LLM_UNAVAILABLE)
            await self._append_degraded(
                state["analysis_id"],
                DegradationFlag.LLM_UNAVAILABLE,
                "interpret",
            )
        adjustment = (
            min(
                self._settings.llm_max_score_adjustment,
                len(interpretation.inconsistencies) * 2,
            )
            if interpretation is not None
            else 0
        )
        final_score = min(100, score.score + adjustment)
        if summary.critical_present:
            final_score = max(final_score, self._scoring_config.critical_floor)
        band = self._band(final_score)
        justification = (
            interpretation.justification
            if interpretation is not None
            else self._fallback_justification(
                state.get("locale", "pt"),
                final_score,
                band,
                len(self._evidence_for(state)),
            )
        )
        inconsistencies = interpretation.inconsistencies if interpretation is not None else ()
        await self._processing(
            state["analysis_id"],
            "interpret",
            {
                "node": "interpret",
                "llm_available": "0" if interpretation is None else "1",
                "adjustment": str(adjustment),
                "final_score": str(final_score),
            },
            flags,
        )
        return {
            "interpretation": interpretation,
            "llm_adjustment": adjustment,
            "final_score": final_score,
            "final_band": band,
            "justification": justification,
            "inconsistencies": inconsistencies,
            "degradation_flags": flags,
        }

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
        model_versions: dict[str, str] = {}
        if fraud.model_version is not None:
            model_versions["ml"] = fraud.model_version
        if interpretation is not None:
            model_versions["llm"] = interpretation.model_version
            model_versions["prompt"] = interpretation.prompt_version
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
            "degradation_flags": ",".join(flag.value for flag in self._flags(state)),
        }

    def _band(self, score: int) -> RiskBand:
        if score <= self._scoring_config.low_max:
            return RiskBand.LOW
        if score <= self._scoring_config.attention_max:
            return RiskBand.ATTENTION
        return RiskBand.HIGH

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
