import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime
from functools import wraps
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any, TypedDict, TypeVar, cast
from uuid import UUID, uuid4

from langgraph.graph import END, StateGraph
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from paysentineliq.application.errors import (
    AnalysisCancelledError,
    AnalysisTimeoutError,
    UnsupportedDocumentError,
)
from paysentineliq.application.ports.analysis import (
    AnalysisDocument,
    AnalysisEventPort,
    AnalysisRepositoryPort,
    document_type_for,
)
from paysentineliq.application.ports.cancellation import CancellationPort, NullCancellation
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
    summary_from_receipt,
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
from paysentineliq.application.security.redaction import (
    escape_delimiters,
    mask_pii,
    mask_terms,
)
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
from paysentineliq.domain.analysis_progress import (
    AnalysisStage,
    progress_within_stage,
    stage_end_percent,
    stage_start_percent,
)
from paysentineliq.domain.boleto.analysis import BoletoAnalysis, analyze_boleto
from paysentineliq.domain.boleto.bank_directory import (
    BankDirectory,
    load_bank_directory,
)
from paysentineliq.domain.boleto.extraction import extract_boleto_fields
from paysentineliq.domain.ingestion import VisualSignal
from paysentineliq.domain.notification import Notification, NotificationType
from paysentineliq.domain.payables import Payable, payable_status_for
from paysentineliq.domain.payslip.analysis import PayslipAnalysis, analyze_payslip
from paysentineliq.domain.payslip.extraction import extract_payslip_fields
from paysentineliq.domain.payslip.regulatory import (
    RegulatoryTables,
    load_regulatory_tables,
)
from paysentineliq.domain.payslip.rules import EvidenceStatus
from paysentineliq.domain.ports.observability import ObservabilityTracer
from paysentineliq.domain.receipt.analysis import ReceiptAnalysis, analyze_receipt
from paysentineliq.domain.receipt.extraction import extract_receipt_fields
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
    receipt_evidence,
    receipt_fields,
)
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.guardrails.training import (
    load_injection_classifier_or_none,
)
from paysentineliq.infrastructure.metrics.guardrails import InMemoryGuardrailMetrics
from paysentineliq.infrastructure.observability.metrics import (
    PlatformMetrics,
    get_platform_metrics,
)
from paysentineliq.infrastructure.observability.noop_tracer import NoopTracer

_T = TypeVar("_T")
_CANCELLATION_POLL_SECONDS = 0.5
_logger = logging.getLogger("paysentineliq")


async def _await_with_cancellation(
    awaitable: Awaitable[_T],
    check: Callable[[], Awaitable[bool]],
) -> _T:
    task = asyncio.ensure_future(awaitable)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=_CANCELLATION_POLL_SECONDS)
            if task in done:
                return await task
            if await check():
                task.cancel()
                with suppress(asyncio.CancelledError, TimeoutError):
                    await asyncio.wait_for(task, timeout=5)
                raise AnalysisCancelledError()
    except asyncio.CancelledError:
        task.cancel()
        with suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(task, timeout=5)
        raise


class AnalysisGraphState(TypedDict, total=False):
    analysis_id: UUID
    document: AnalysisDocument
    data: bytes
    locale: str
    ocr_text: str
    ocr_page_count: int
    ocr_block_count: int
    ocr_text_chars: int
    sanitized_text: str
    visual_signals: tuple[VisualSignal, ...]
    document_type: AnalysisDocumentType
    boleto_analysis: BoletoAnalysis | None
    payslip_analysis: PayslipAnalysis | None
    receipt_analysis: ReceiptAnalysis | None
    deterministic_summary: DeterministicSummary | None
    fraud_score: FraudScore | None
    rag_passages: tuple[RetrievedPassage, ...]
    rag_retrieval_mode: str
    rerank_applied: bool
    rerank_fallback: str | None
    rerank_model: str | None
    rerank_top1_changed: bool | None
    rerank_order_before: tuple[str, ...]
    rerank_order_after: tuple[str, ...]
    rerank_latency_ms: float | None
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
        platform_metrics: PlatformMetrics | None = None,
        cancellation: CancellationPort | None = None,
        tracer: ObservabilityTracer | None = None,
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
        self._platform_metrics = (
            platform_metrics if platform_metrics is not None else get_platform_metrics()
        )
        self._cancellation = cancellation or NullCancellation()
        self._tracer = trace.get_tracer("paysentineliq")
        self._observability = tracer or NoopTracer()
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
        graph.add_node("load", self._observed("load", self._load_node))
        graph.add_node("ingest", self._observed("ingest", self._ingest_node))
        graph.add_node("guard", self._observed("guard", self._guard_node))
        graph.add_node("classify", self._observed("classify", self._classify_node))
        graph.add_node("boleto", self._observed("boleto", self._boleto_node))
        graph.add_node("payslip", self._observed("payslip", self._payslip_node))
        graph.add_node("receipt", self._observed("receipt", self._receipt_node))
        graph.add_node("fraud", self._observed("fraud", self._fraud_node))
        graph.add_node("rag", self._observed("rag", self._rag_node))
        graph.add_node("interpret", self._observed("interpret", self._interpret_node))
        graph.add_node("persist", self._observed("persist", self._persist_node))
        graph.set_entry_point("load")
        graph.add_edge("load", "ingest")
        graph.add_edge("ingest", "guard")
        graph.add_edge("guard", "classify")
        graph.add_conditional_edges(
            "classify",
            self._route_document,
            {"boleto": "boleto", "payslip": "payslip", "receipt": "receipt"},
        )
        graph.add_edge("boleto", "fraud")
        graph.add_edge("payslip", "fraud")
        graph.add_edge("receipt", "fraud")
        graph.add_edge("fraud", "rag")
        graph.add_edge("rag", "interpret")
        graph.add_edge("interpret", "persist")
        graph.add_edge("persist", END)
        return graph.compile()

    def _observed(
        self,
        stage: str,
        node: Callable[[AnalysisGraphState], Awaitable[AnalysisGraphState]],
    ) -> Callable[[AnalysisGraphState], Awaitable[AnalysisGraphState]]:
        @wraps(node)
        async def wrapper(state: AnalysisGraphState) -> AnalysisGraphState:
            started = perf_counter()
            document_type = self._metric_document_type(state)
            result: AnalysisGraphState = {}
            with self._tracer.start_as_current_span(f"pipeline.{stage}") as span:
                span.set_attribute("pipeline.stage", stage)
                span.set_attribute("document.type", document_type)
                try:
                    if stage == "persist":
                        await self._ensure_not_cancelled(state["analysis_id"])
                        result = await node(state)
                    else:
                        result = await _await_with_cancellation(
                            node(state),
                            lambda: self._is_cancelled(state["analysis_id"]),
                        )
                except Exception:
                    span.set_status(Status(StatusCode.ERROR))
                    raise
                finally:
                    self._platform_metrics.record_pipeline_stage(
                        stage,
                        document_type,
                        perf_counter() - started,
                    )
            return result

        return wrapper

    def _metric_document_type(self, state: AnalysisGraphState) -> str:
        document = state.get("document")
        if document is None:
            return "other"
        document_type = document_type_for(document.kind)
        return document_type.value if document_type is not None else "other"

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
        await self._ensure_not_cancelled(analysis_id)
        await self._begin_stage(analysis_id, AnalysisStage.VALIDATION, "Validando o arquivo")
        document_type = self._metric_document_type(initial)
        with self._tracer.start_as_current_span("pipeline.run") as span:
            span.set_attribute("document.type", document_type)
            otel_trace_id = format(span.get_span_context().trace_id, "032x")
            span.set_attribute("analysis.id", str(analysis_id))
            with self._observability.trace(
                "analysis",
                session_id=str(analysis_id),
                metadata={
                    "analysis_id": str(analysis_id),
                    "document_id": str(document.id),
                    "document_type": document_type,
                    "otel_trace_id": otel_trace_id,
                    "environment": self._settings.app_env,
                },
                tags=("analysis", f"env:{self._settings.app_env}"),
                environment=self._settings.app_env,
                input={
                    "document_type": document_type,
                    "document_id": str(document.id),
                    "locale": locale,
                },
            ) as trace_handle:
                langfuse_trace_id = self._observability.current_trace_id()
                span.set_attribute("langfuse.trace_id", langfuse_trace_id or "")
                result: Any = await self._graph.ainvoke(initial)
                final_state = cast(AnalysisGraphState, result if isinstance(result, dict) else {})
                report = final_state.get("report")
                if not isinstance(report, AnalysisReport):
                    raise RuntimeError("analysis did not produce a report")
                flags = final_state.get("degradation_flags", ())
                guardrail_failed = self._guardrail_failed(final_state)
                rerank_changed = final_state.get("rerank_top1_changed")
                trace_handle.update(
                    output={
                        "score": report.score,
                        "band": report.band.value,
                        "evidence_count": len(report.evidence),
                        "degradation_flags": [flag.value for flag in flags],
                        "guardrail_failed": guardrail_failed,
                        "rerank_alterou_top1": bool(rerank_changed),
                        "rerank_applied": bool(final_state.get("rerank_applied", False)),
                    },
                    metadata={
                        "otel_trace_id": otel_trace_id,
                        "llm_adjustment": final_state.get("llm_adjustment"),
                        "retrieval_mode": final_state.get("rag_retrieval_mode"),
                        "rerank_fallback": final_state.get("rerank_fallback"),
                    },
                )
                self._score_trace(report, final_state, guardrail_failed)
                _logger.info(
                    "analysis_trace",
                    extra={
                        "event": "analysis_trace",
                        "analysis_id": str(analysis_id),
                        "otel_trace_id": otel_trace_id,
                        "langfuse_trace_id": langfuse_trace_id,
                    },
                )
                return report

    def _guardrail_failed(self, state: AnalysisGraphState) -> bool:
        findings = state.get("guardrail_findings", ())
        flags = set(state.get("degradation_flags", ()))
        blocking_flags = {
            DegradationFlag.PROMPT_INJECTION_DETECTED,
            DegradationFlag.LLM_OUTPUT_REJECTED,
            DegradationFlag.LLM_JUDGE_REJECTED,
        }
        return bool(findings) or bool(flags & blocking_flags)

    def _score_trace(
        self,
        report: AnalysisReport,
        state: AnalysisGraphState,
        guardrail_failed: bool,
    ) -> None:
        self._observability.score(
            "risk_score",
            float(report.score),
            data_type="NUMERIC",
        )
        self._observability.score(
            "risk_band",
            report.band.value,
            data_type="CATEGORICAL",
        )
        self._observability.score(
            "rerank_alterou_top1",
            1.0 if state.get("rerank_top1_changed") else 0.0,
            data_type="BOOLEAN",
        )
        self._observability.score(
            "rerank_applied",
            1.0 if state.get("rerank_applied") else 0.0,
            data_type="BOOLEAN",
        )
        self._observability.score(
            "guardrail_failed",
            1.0 if guardrail_failed else 0.0,
            data_type="BOOLEAN",
        )
        verdict = state.get("judge_verdict")
        if isinstance(verdict, JudgeVerdict):
            self._observability.score(
                "judge_approved",
                1.0 if verdict.approved else 0.0,
                data_type="BOOLEAN",
            )
            self._observability.score(
                "judge_verdict",
                verdict.reason,
                data_type="CATEGORICAL",
            )
            self._observability.score(
                "judge_findings",
                float(len(verdict.findings)),
                data_type="NUMERIC",
            )

    async def _load_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        document = state["document"]
        await self._complete_stage(
            state["analysis_id"],
            AnalysisStage.VALIDATION,
            f"Arquivo recebido ({document.kind.value})",
        )
        return {}

    async def _ingest_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        analysis_id = state["analysis_id"]
        await self._begin_stage(analysis_id, AnalysisStage.OCR, "Lendo o documento")

        async def _on_page(page: int, total: int) -> None:
            await self._report_progress(
                analysis_id,
                AnalysisStage.OCR,
                progress_within_stage(AnalysisStage.OCR, page / max(1, total)),
                f"Página {page} de {total}",
            )

        try:
            with self._observability.observation(
                "ocr",
                as_type="span",
                input={
                    "document_type": self._metric_document_type(state),
                    "bytes": len(state["data"]),
                },
                metadata={
                    "languages": list(self._settings.ocr_languages_list),
                    "max_pages": self._settings.ocr_max_pages,
                },
            ) as observation:
                result = await asyncio.wait_for(
                    self._ingestion.ingest(
                        state["data"],
                        on_page=_on_page,
                        check_cancelled=lambda: self._is_cancelled(analysis_id),
                    ),
                    timeout=self._node_timeout,
                )
                text = "\n".join(block.text for block in result.blocks)
                observation.update(
                    output={
                        "page_count": result.page_count,
                        "block_count": len(result.blocks),
                        "text_chars": len(text),
                        "visual_signal_count": len(result.signals),
                    },
                )
        except TimeoutError as exc:
            raise AnalysisTimeoutError("ingest") from exc
        await self._complete_stage(
            analysis_id,
            AnalysisStage.OCR,
            f"{result.page_count} página(s) lida(s)",
        )
        return {
            "ocr_text": text,
            "visual_signals": result.signals,
            "ocr_page_count": result.page_count,
            "ocr_block_count": len(result.blocks),
            "ocr_text_chars": len(text),
        }

    async def _guard_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        with self._observability.observation(
            "guardrail.input",
            as_type="guardrail",
            input={"text_chars": len(state["ocr_text"])},
            metadata={"classifier_enabled": self._classifier_enabled},
        ) as observation:
            result = self._input_guard.inspect(state["ocr_text"])
            observation.update(
                output={
                    "triggered": result.triggered,
                    "findings": [finding.code for finding in result.findings],
                    "classifier_version": result.classifier_version,
                    "classifier_unavailable": result.classifier_unavailable,
                },
            )
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
        await self._report_progress(
            state["analysis_id"],
            AnalysisStage.OCR,
            stage_end_percent(AnalysisStage.OCR),
            "Verificando segurança do texto",
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
        with self._observability.observation(
            "classifier.document",
            as_type="span",
            input={"kind": document.kind.value},
        ) as observation:
            document_type = document_type_for(document.kind)
            if document_type is None:
                raise UnsupportedDocumentError()
            observation.update(output={"document_type": document_type.value})
        await self._begin_stage(
            state["analysis_id"],
            AnalysisStage.EXTRACTION,
            "Identificando o tipo de documento",
        )
        return {"document_type": document_type}

    def _route_document(self, state: AnalysisGraphState) -> str:
        document_type = state.get("document_type")
        if document_type is None:
            raise UnsupportedDocumentError()
        return document_type.value

    async def _boleto_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
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
        await self._complete_stage(
            state["analysis_id"],
            AnalysisStage.EXTRACTION,
            f"Regras aplicadas ({len(analysis.evidence)} evidências)",
        )
        return {
            "boleto_analysis": analysis,
            "deterministic_summary": summary,
        }

    async def _payslip_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
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
        await self._complete_stage(
            state["analysis_id"],
            AnalysisStage.EXTRACTION,
            f"Regras aplicadas ({len(analysis.evidence)} evidências)",
        )
        return {
            "payslip_analysis": analysis,
            "deterministic_summary": summary,
        }

    async def _receipt_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        try:
            analysis, summary = await asyncio.wait_for(
                asyncio.to_thread(self._run_receipt, state["ocr_text"]),
                timeout=self._node_timeout,
            )
        except TimeoutError as exc:
            raise AnalysisTimeoutError("receipt") from exc
        await self._append_rule_events(
            state["analysis_id"],
            analysis.evidence,
            analysis.rule_set_version,
        )
        await self._complete_stage(
            state["analysis_id"],
            AnalysisStage.EXTRACTION,
            f"Regras aplicadas ({len(analysis.evidence)} evidências)",
        )
        return {
            "receipt_analysis": analysis,
            "deterministic_summary": summary,
        }

    async def _fraud_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        summary = state.get("deterministic_summary")
        if summary is None:
            raise RuntimeError("deterministic summary is missing")
        flags = self._flags(state)
        await self._begin_stage(
            state["analysis_id"],
            AnalysisStage.CLASSIFICATION,
            "Calculando o score de risco",
        )
        try:
            with self._observability.observation(
                "classifier.risk",
                as_type="span",
                input={
                    "document_type": summary.document_type,
                    "evidence_count": len(summary.evidence),
                },
            ) as observation:
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
                observation.update(
                    output={
                        "score": score.score,
                        "band": score.band.value,
                        "ml_unavailable": score.ml_unavailable,
                        "critical_floor_applied": score.critical_floor_applied,
                        "model_version": score.model_version,
                    },
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
        await self._complete_stage(
            state["analysis_id"],
            AnalysisStage.CLASSIFICATION,
            f"Score calculado ({score.score})",
        )
        return {"fraud_score": score, "degradation_flags": flags}

    async def _rag_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        flags = self._flags(state)
        await self._begin_stage(
            state["analysis_id"],
            AnalysisStage.RAG,
            "Consultando a base de conhecimento e reranqueando",
        )
        query_text = self._rag_query(state)
        limit = self._settings.retrieval_top_k if self._settings.hybrid_retrieval_enabled else 5
        with self._observability.observation(
            "retrieval",
            as_type="retriever",
            input={"query": query_text, "limit": limit},
            metadata={
                "hybrid_retrieval": self._settings.hybrid_retrieval_enabled,
                "rerank_enabled": self._settings.rerank_enabled,
            },
        ) as observation:
            try:
                result = await asyncio.wait_for(
                    self._retriever.retrieve(
                        KnowledgeQuery(
                            text=query_text,
                            as_of=self._clock().date(),
                            limit=limit,
                        ),
                    ),
                    timeout=self._node_timeout,
                )
            except Exception:
                observation.update(
                    output={
                        "rag_unavailable": True,
                        "reason": "rag_unavailable",
                    },
                )
                flags = self._add_flag(flags, DegradationFlag.RAG_UNAVAILABLE)
                await self._append_degraded(
                    state["analysis_id"],
                    DegradationFlag.RAG_UNAVAILABLE,
                    "rag",
                )
                await self._complete_stage(
                    state["analysis_id"],
                    AnalysisStage.RAG,
                    "Base de conhecimento indisponível",
                )
                return {
                    "rag_passages": (),
                    "degradation_flags": flags,
                    "rag_retrieval_mode": "unavailable",
                    "rerank_applied": False,
                    "rerank_fallback": "rag_unavailable",
                    "rerank_model": None,
                    "rerank_top1_changed": False,
                    "rerank_order_before": (),
                    "rerank_order_after": (),
                    "rerank_latency_ms": None,
                }
            observation.update(
                output={
                    "rag_unavailable": result.rag_unavailable,
                    "passages": self._passages_for_trace(result.passages),
                    "retrieval_mode": result.retrieval_mode,
                    "rerank_applied": result.rerank_applied,
                    "rerank_fallback": result.rerank_fallback,
                    "rerank_model": result.rerank_model,
                    "rerank_top1_changed": result.rerank_top1_changed,
                    "rerank_order_before": list(result.rerank_rank_before),
                    "rerank_order_after": list(result.rerank_rank_after),
                    "rerank_latency_ms": result.rerank_latency_ms,
                },
            )
            if result.rag_unavailable:
                flags = self._add_flag(flags, DegradationFlag.RAG_UNAVAILABLE)
                await self._append_degraded(
                    state["analysis_id"],
                    DegradationFlag.RAG_UNAVAILABLE,
                    "rag",
                )
        await self._complete_stage(
            state["analysis_id"],
            AnalysisStage.RAG,
            f"{len(result.passages)} trecho(s) recuperado(s)",
        )
        return {
            "rag_passages": result.passages,
            "degradation_flags": flags,
            "rag_retrieval_mode": result.retrieval_mode,
            "rerank_applied": result.rerank_applied,
            "rerank_fallback": result.rerank_fallback,
            "rerank_model": result.rerank_model,
            "rerank_top1_changed": result.rerank_top1_changed,
            "rerank_order_before": result.rerank_rank_before,
            "rerank_order_after": result.rerank_rank_after,
            "rerank_latency_ms": result.rerank_latency_ms,
        }

    @staticmethod
    def _passages_for_trace(
        passages: tuple[RetrievedPassage, ...],
    ) -> list[dict[str, object]]:
        return [
            {
                "document_key": passage.citation.document_key,
                "score": passage.score,
                "dense_score": passage.dense_score,
                "sparse_score": passage.sparse_score,
                "fused_score": passage.fused_score,
                "dense_rank": passage.dense_rank,
                "sparse_rank": passage.sparse_rank,
                "rerank_score": passage.rerank_score,
            }
            for passage in passages
        ]

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
        await self._begin_stage(
            state["analysis_id"],
            AnalysisStage.LLM,
            "Gerando a justificativa",
        )

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
                with self._observability.observation(
                    "guardrail.output",
                    as_type="guardrail",
                    input={
                        "justification_chars": len(interpretation.justification),
                        "inconsistencies": len(interpretation.inconsistencies),
                    },
                ) as observation:
                    scanned, blocked, scan_findings = self._scan_interpretation(
                        state,
                        interpretation,
                    )
                    observation.update(
                        output={
                            "blocked": blocked,
                            "findings": [finding.code for finding in scan_findings],
                        },
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
                    self._platform_metrics.record_guardrail_block(
                        GUARDRAIL_LAYER_OUTPUT,
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
            await self._report_progress(
                state["analysis_id"],
                AnalysisStage.LLM,
                stage_start_percent(AnalysisStage.LLM),
                "Revisando a resposta do modelo",
            )
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
        await self._complete_stage(
            state["analysis_id"],
            AnalysisStage.LLM,
            "Justificativa pronta",
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
            with self._observability.observation(
                "guardrail.judge",
                as_type="evaluator",
                input={"available": False},
            ) as observation:
                observation.update(output={"available": False, "reason": "disabled"})
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
        with self._observability.observation(
            "guardrail.judge",
            as_type="evaluator",
            input={
                "candidate_score": candidate_score,
                "evidence_count": len(evidence),
                "justification_chars": len(interpretation.justification),
            },
            metadata={"band": candidate_band.value},
        ) as observation:
            try:
                verdict = await asyncio.wait_for(
                    self._judge.judge(request),
                    timeout=self._node_timeout,
                )
            except Exception:
                observation.update(
                    level="WARNING",
                    status_message="judge_unavailable",
                )
                flags = self._add_flag(flags, DegradationFlag.LLM_JUDGE_UNAVAILABLE)
                await self._append_degraded(
                    state["analysis_id"],
                    DegradationFlag.LLM_JUDGE_UNAVAILABLE,
                    "interpret",
                )
                self._metrics.record(GUARDRAIL_LAYER_JUDGE, "unavailable")
                return None, flags, evidence, True
            observation.update(
                output={
                    "approved": verdict.approved,
                    "verdict_reason": verdict.reason,
                    "findings_count": len(verdict.findings),
                },
            )
        self._metrics.record(
            GUARDRAIL_LAYER_JUDGE,
            "approved" if verdict.approved else "rejected",
        )
        if not verdict.approved:
            self._platform_metrics.record_guardrail_block(GUARDRAIL_LAYER_JUDGE)
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

    def _payable_for_receipt(
        self,
        state: AnalysisGraphState,
        receipt: ReceiptAnalysis,
        analysis_id: UUID,
        owner_id: UUID,
    ) -> Payable | None:
        amount = receipt.fields.amount
        due_date = receipt.fields.due_date
        if amount is None or amount.confidence < 0.5 or amount.value <= 0:
            return None
        if due_date is None or due_date.confidence < 0.5:
            return None
        status = payable_status_for(
            state.get("final_band", RiskBand.LOW),
            injection_detected=bool(state.get("input_guard_triggered", False)),
        )
        if status is None:
            return None
        cents = int((amount.value * 100).to_integral_value())
        if cents <= 0:
            return None
        issuer = receipt.fields.issuer.value if receipt.fields.issuer is not None else ""
        reference = receipt.fields.reference.value if receipt.fields.reference is not None else ""
        description = (
            " - ".join(part for part in (issuer.strip(), reference.strip()) if part)
            or "Conta de consumo"
        )
        now = self._clock()
        return Payable(
            id=uuid4(),
            owner_id=owner_id,
            analysis_id=analysis_id,
            description=description[:200],
            amount_cents=cents,
            due_date=due_date.value,
            status=status,
            created_at=now,
            updated_at=now,
        )

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
        masked = escape_delimiters(mask_terms(mask_pii(text), self._sensitive_terms(state)))
        return masked[: self._settings.guardrail_llm_excerpt_chars]

    async def _persist_node(self, state: AnalysisGraphState) -> AnalysisGraphState:
        boleto = state.get("boleto_analysis")
        payslip = state.get("payslip_analysis")
        receipt = state.get("receipt_analysis")
        fraud = state.get("fraud_score")
        if boleto is None and payslip is None and receipt is None:
            raise RuntimeError("analysis result is missing")
        if fraud is None:
            raise RuntimeError("fraud score is missing")
        analysis_id = state["analysis_id"]
        document = state["document"]
        flags = self._flags(state)
        interpretation = state.get("interpretation")
        await self._begin_stage(
            analysis_id,
            AnalysisStage.PERSISTENCE,
            "Salvando o resultado",
        )
        if boleto is not None:
            fields = boleto_fields(boleto)
            evidence = boleto_evidence(boleto)
            rule_set_version = boleto.rule_set_version
            document_type = AnalysisDocumentType.BOLETO
        elif payslip is not None:
            fields = payslip_fields(payslip)
            evidence = payslip_evidence(payslip)
            rule_set_version = payslip.rule_set_version
            document_type = AnalysisDocumentType.PAYSLIP
        else:
            if receipt is None:
                raise RuntimeError("receipt analysis is missing")
            fields = receipt_fields(receipt)
            evidence = receipt_evidence(receipt)
            rule_set_version = receipt.rule_set_version
            document_type = AnalysisDocumentType.RECEIPT
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
        payables: tuple[Payable, ...] = ()
        if receipt is not None:
            payable = self._payable_for_receipt(
                state,
                receipt,
                analysis_id,
                document.owner_id,
            )
            if payable is not None:
                payables = (payable,)
        terminal_status = AnalysisStatus.DEGRADED if flags else AnalysisStatus.COMPLETED
        notification_type = NotificationType.ANALYSIS_COMPLETED
        if report.band is RiskBand.HIGH:
            notification_type = NotificationType.HIGH_RISK_DETECTED
        elif document_type is AnalysisDocumentType.RECEIPT:
            notification_type = NotificationType.RECEIPT_ANALYZED
        notification = Notification(
            id=uuid4(),
            owner_id=document.owner_id,
            analysis_id=analysis_id,
            type=notification_type,
            payload={
                "analysis_id": str(analysis_id),
                "document_type": document_type.value,
                "status": terminal_status.value,
                "score": str(report.score),
                "band": report.band.value,
            },
            created_at=self._clock(),
        )
        await self._report_progress(
            analysis_id,
            AnalysisStage.PERSISTENCE,
            stage_end_percent(AnalysisStage.PERSISTENCE),
            "Resultado pronto para finalizar",
        )
        completed = await self._analyses.complete(
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
            event=AnalysisEvent(
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
            notifications=(notification,),
            payables=payables,
        )
        if not completed:
            with suppress(Exception):
                await self._storage.delete(report_key)
            raise AnalysisCancelledError(analysis_id)
        self._platform_metrics.record_analysis(document_type.value, report.band.value)
        self._platform_metrics.record_notification("in_app", "created")
        return {"report": report}

    async def _is_cancelled(self, analysis_id: UUID) -> bool:
        return await self._cancellation.is_cancelled(analysis_id)

    async def _ensure_not_cancelled(self, analysis_id: UUID) -> None:
        if await self._is_cancelled(analysis_id):
            raise AnalysisCancelledError(analysis_id)

    async def _report_progress(
        self,
        analysis_id: UUID,
        stage: AnalysisStage,
        percent: int,
        detail: str | None,
    ) -> None:
        with suppress(Exception):
            await self._analyses.report_progress(
                analysis_id,
                stage=stage,
                percent=percent,
                detail=detail,
                event=AnalysisEvent(
                    analysis_id=analysis_id,
                    event_type=AnalysisEventType.PROGRESS,
                    payload={
                        "stage": stage.value,
                        "percent": str(percent),
                        "detail": (detail or "")[:120],
                    },
                ),
            )

    async def _begin_stage(
        self,
        analysis_id: UUID,
        stage: AnalysisStage,
        detail: str | None,
    ) -> None:
        await self._report_progress(
            analysis_id,
            stage,
            stage_start_percent(stage),
            detail,
        )

    async def _complete_stage(
        self,
        analysis_id: UUID,
        stage: AnalysisStage,
        detail: str | None,
    ) -> None:
        await self._report_progress(
            analysis_id,
            stage,
            stage_end_percent(stage),
            detail,
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
            self._platform_metrics.record_guardrail_block(finding.layer)
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

    def _run_receipt(
        self,
        text: str,
    ) -> tuple[ReceiptAnalysis, DeterministicSummary]:
        analysis = analyze_receipt(
            extract_receipt_fields(text, bank_directory=self._bank_directory),
        )
        return analysis, summary_from_receipt(analysis)

    def _document_type(self, document: AnalysisDocument) -> AnalysisDocumentType | None:
        if document.kind.value == "bank_slip":
            return AnalysisDocumentType.BOLETO
        if document.kind.value == "payslip":
            return AnalysisDocumentType.PAYSLIP
        if document.kind.value == "receipt":
            return AnalysisDocumentType.RECEIPT
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
        receipt = state.get("receipt_analysis")
        if receipt is not None:
            return tuple(
                InterpretationEvidence(
                    rule_id=item.rule_id,
                    severity=item.severity.value,
                    weight=item.weight,
                    message_key=item.message_key,
                )
                for item in receipt.evidence
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
