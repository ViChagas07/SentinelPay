import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, BinaryIO
from uuid import UUID, uuid4

import pytest

from paysentineliq.application.errors import (
    AnalysisCancelledError,
    AnalysisTimeoutError,
    LlmUnavailableError,
)
from paysentineliq.application.ports.analysis import AnalysisDocument
from paysentineliq.application.ports.fraud_model import ModelPrediction
from paysentineliq.application.ports.guardrails import JudgeVerdict
from paysentineliq.application.queries.fraud_scoring import FraudScoringService
from paysentineliq.application.queries.knowledge_retrieval import (
    KnowledgeCitation,
    KnowledgeQuery,
    KnowledgeRetrievalResult,
    RetrievedPassage,
)
from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisEvent,
    AnalysisEventType,
    AnalysisStatus,
    DegradationFlag,
)
from paysentineliq.domain.analysis_progress import AnalysisStage
from paysentineliq.domain.document import DocumentKind
from paysentineliq.domain.ingestion import IngestionResult, TextBlock, VisualSignal
from paysentineliq.domain.knowledge import (
    Provenance,
)
from paysentineliq.domain.notification import NotificationType
from paysentineliq.domain.payslip.regulatory import RegulatoryTables
from paysentineliq.domain.scoring import RiskBand, ScoringConfig, fuse_risk
from paysentineliq.infrastructure.ai.graph import LangGraphAnalysisOrchestrator
from paysentineliq.infrastructure.config import Settings
from tests.support.boleto_factory import build_boleto, format_line
from tests.support.payslip_factory import SyntheticPayslip
from tests.support.regulatory_factory import synthetic_regulatory_tables

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeIngestion:
    def __init__(self, text: str, *, delay: float = 0.0) -> None:
        self._text = text
        self._delay = delay
        self.calls = 0

    async def ingest(
        self,
        data: bytes,
        *,
        on_page: Callable[[int, int], Awaitable[None]] | None = None,
        check_cancelled: Callable[[], Awaitable[bool]] | None = None,
    ) -> IngestionResult:
        self.calls += 1
        if check_cancelled is not None and await check_cancelled():
            raise RuntimeError("cancelled")
        if self._delay:
            await asyncio.sleep(self._delay)
        if on_page is not None:
            await on_page(1, 1)
        return IngestionResult(
            blocks=(TextBlock(text=self._text, page=1, bbox=None, confidence=1.0),),
            signals=(VisualSignal(name="image_blur", value=0.0, explanation="none"),),
            page_count=1,
            used_ocr=False,
            source_type="pdf_native",
            language=None,
        )


class FakeRag:
    def __init__(self, result: KnowledgeRetrievalResult) -> None:
        self._result = result
        self.query: KnowledgeQuery | None = None

    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeRetrievalResult:
        self.query = query
        return self._result


class FakeCancellation:
    def __init__(self, *, cancelled: bool = False) -> None:
        self.cancelled = cancelled
        self.requests: list[UUID] = []
        self.cleared: list[UUID] = []

    async def request(self, analysis_id: UUID) -> None:
        self.requests.append(analysis_id)

    async def clear(self, analysis_id: UUID) -> None:
        self.cleared.append(analysis_id)

    async def is_cancelled(self, analysis_id: UUID) -> bool:
        return self.cancelled


class FakeInterpreter:
    def __init__(
        self,
        *,
        inconsistencies: tuple[str, ...] = ("Possivel inconsistencia.",),
        error: Exception | None = None,
    ) -> None:
        self._inconsistencies = inconsistencies
        self._error = error
        self.request: Any = None

    async def interpret(self, request: Any) -> Any:
        self.request = request
        if self._error is not None:
            raise self._error
        from paysentineliq.application.ports.interpretation import InterpretationResult

        return InterpretationResult(
            justification="Justificativa fake.",
            inconsistencies=self._inconsistencies,
            model_version="fake-llm",
            prompt_version="p11-test",
        )


class FakeObservation:
    def __init__(self, updates: list[dict[str, Any]], name: str) -> None:
        self._updates = updates
        self._name = name

    def update(
        self,
        *,
        output: Any = None,
        metadata: Mapping[str, Any] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        self._updates.append(
            {
                "name": self._name,
                "output": output,
                "metadata": metadata,
                "level": level,
                "status_message": status_message,
            },
        )


class FakeObservability:
    def __init__(self) -> None:
        self.traces: list[dict[str, Any]] = []
        self.spans: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []
        self.scores: list[dict[str, Any]] = []

    @contextmanager
    def trace(
        self,
        name: str,
        *,
        session_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        tags: tuple[str, ...] = (),
        environment: str | None = None,
        input: Any = None,
    ) -> Iterator[FakeObservation]:
        self.traces.append(
            {
                "name": name,
                "session_id": session_id,
                "metadata": metadata,
                "tags": tags,
                "environment": environment,
                "input": input,
            },
        )
        yield FakeObservation(self.updates, name)

    @contextmanager
    def observation(
        self,
        name: str,
        *,
        as_type: str = "generation",
        input: Any = None,
        metadata: Mapping[str, Any] | None = None,
        model: str | None = None,
    ) -> Iterator[FakeObservation]:
        self.spans.append(
            {
                "name": name,
                "as_type": as_type,
                "input": input,
                "metadata": metadata,
                "model": model,
            },
        )
        yield FakeObservation(self.updates, name)

    def score(
        self,
        name: str,
        value: float | str,
        *,
        data_type: str | None = None,
        comment: str | None = None,
    ) -> None:
        self.scores.append(
            {
                "name": name,
                "value": value,
                "data_type": data_type,
                "comment": comment,
            },
        )

    def current_trace_id(self) -> str | None:
        return "langfuse-trace-1"

    async def flush(self) -> None:
        return None

    async def aclose(self) -> None:
        return None


class FakeJudge:
    async def judge(self, request: Any) -> JudgeVerdict:
        return JudgeVerdict(
            approved=True,
            reason="anchored",
            findings=(),
            model_version="fake-judge",
            prompt_version="j1-test",
        )


class FakeModel:
    def __init__(
        self,
        *,
        probability: float = 0.1,
        anomaly_score: float = 0.1,
        error: Exception | None = None,
    ) -> None:
        self._probability = probability
        self._anomaly_score = anomaly_score
        self._error = error
        self.calls = 0

    @property
    def available(self) -> bool:
        return True

    def predict(self, features: tuple[float, ...]) -> ModelPrediction:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return ModelPrediction(
            probability=self._probability,
            anomaly_score=self._anomaly_score,
            model_version="fake-ml",
            synthetic=True,
        )


class FakeAnalysisRepository:
    def __init__(self) -> None:
        self.states: list[dict[str, Any]] = []
        self.progress: list[dict[str, Any]] = []
        self.completed: dict[str, Any] | None = None
        self.failed: dict[str, Any] | None = None
        self.cancelled = False

    async def create(
        self,
        record: Any,
        *,
        event: AnalysisEvent | None = None,
    ) -> None:
        return None

    async def update_state(
        self,
        analysis_id: UUID,
        *,
        status: AnalysisStatus,
        state: Mapping[str, object],
        degradation_flags: tuple[DegradationFlag, ...],
        event: AnalysisEvent | None = None,
    ) -> bool:
        self.states.append(
            {
                "analysis_id": analysis_id,
                "status": status,
                "state": dict(state),
                "flags": degradation_flags,
            },
        )
        return True

    async def complete(
        self,
        analysis_id: UUID,
        *,
        score: int,
        band: RiskBand,
        rule_set_version: str,
        model_versions: Mapping[str, str],
        degradation_flags: tuple[DegradationFlag, ...],
        state: Mapping[str, object],
        report_s3_key: str,
        event: AnalysisEvent | None = None,
        notifications: tuple[Any, ...] = (),
        payables: tuple[Any, ...] = (),
    ) -> bool:
        self.completed = {
            "analysis_id": analysis_id,
            "score": score,
            "band": band,
            "rule_set_version": rule_set_version,
            "model_versions": dict(model_versions),
            "flags": degradation_flags,
            "state": dict(state),
            "report_s3_key": report_s3_key,
            "event": event,
            "notifications": notifications,
            "payables": payables,
        }
        return True

    async def fail(
        self,
        analysis_id: UUID,
        *,
        error_code: str,
        state: Mapping[str, object],
        event: AnalysisEvent | None = None,
        notifications: tuple[Any, ...] = (),
        payables: tuple[Any, ...] = (),
    ) -> bool:
        self.failed = {"analysis_id": analysis_id, "error_code": error_code}
        return True

    async def requeue_for_retry(
        self,
        analysis_id: UUID,
        *,
        error_code: str,
        state: Mapping[str, object],
        event: AnalysisEvent,
    ) -> bool:
        return True

    async def claim_for_processing(
        self,
        analysis_id: UUID,
        *,
        task_id: str,
        lease_seconds: int,
        event: AnalysisEvent | None = None,
    ) -> Any:
        return None

    async def get(self, analysis_id: UUID) -> Any:
        return None

    async def find_by_idempotency(self, owner_id: UUID, idempotency_key: str) -> Any:
        return None

    async def count_active_for_owner(self, owner_id: UUID) -> int:
        return 0

    async def list_stale_processing(self, before: datetime) -> tuple[Any, ...]:
        return ()

    async def report_progress(
        self,
        analysis_id: UUID,
        *,
        stage: AnalysisStage,
        percent: int,
        detail: str | None,
        event: AnalysisEvent | None = None,
    ) -> bool:
        self.progress.append(
            {
                "analysis_id": analysis_id,
                "stage": stage,
                "percent": percent,
                "detail": detail,
                "event": event,
            },
        )
        return True

    async def finalize_cancelled(
        self,
        analysis_id: UUID,
        *,
        event: AnalysisEvent | None = None,
    ) -> bool:
        self.cancelled = True
        return True


class FakeEventRepository:
    def __init__(self) -> None:
        self.events: list[AnalysisEvent] = []

    async def append(self, event: AnalysisEvent) -> None:
        self.events.append(event)


class FakeStorage:
    def __init__(self) -> None:
        self.puts: list[dict[str, Any]] = []

    async def put(
        self,
        key: str,
        stream: BinaryIO,
        *,
        content_type: str,
        size: int,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        self.puts.append(
            {
                "key": key,
                "data": stream.read(),
                "content_type": content_type,
                "size": size,
                "metadata": dict(metadata or {}),
            },
        )

    async def get_stream(self, key: str) -> AsyncIterator[bytes]:
        yield b""

    async def delete(self, key: str) -> None:
        return None

    async def presigned_get_url(self, key: str, *, expires_in: int) -> str:
        return f"https://storage.example/{key}"


def _settings(*, node_timeout: float = 60.0) -> Settings:
    return Settings(
        app_env="local",
        jwt_secret="s" * 64,
        security_hash_secret="h" * 32,
        ai_node_timeout_seconds=node_timeout,
    )


def _document(kind: DocumentKind) -> AnalysisDocument:
    return AnalysisDocument(
        id=uuid4(),
        owner_id=uuid4(),
        kind=kind,
        s3_key="users/owner/bank_slip/analysis/original.pdf",
        content_type="application/pdf",
        size=10,
    )


def _passage() -> RetrievedPassage:
    return RetrievedPassage(
        content="Trecho de conhecimento.",
        citation=KnowledgeCitation(
            document_key="febraban/manual.pdf",
            path="knowledge/febraban/manual.pdf",
            title="Manual",
            category="febraban",
            section="page 1",
            provenance=Provenance.UNKNOWN,
            source="unknown",
            version=None,
            authoritative=False,
        ),
        score=0.9,
    )


def _rag_result(*, unavailable: bool = False) -> KnowledgeRetrievalResult:
    passage = _passage()
    return KnowledgeRetrievalResult(
        passages=() if unavailable else (passage,),
        rag_unavailable=unavailable,
        reason="rag_unavailable" if unavailable else None,
    )


def _orchestrator(
    text: str,
    *,
    kind: DocumentKind = DocumentKind.BANK_SLIP,
    model: FakeModel | None = None,
    rag: FakeRag | None = None,
    interpreter: FakeInterpreter | None = None,
    settings: Settings | None = None,
    regulatory: RegulatoryTables | None = None,
    ingestion_delay: float = 0.0,
    cancellation: FakeCancellation | None = None,
    judge: Any = None,
    observability: Any = None,
) -> tuple[
    LangGraphAnalysisOrchestrator,
    FakeAnalysisRepository,
    FakeEventRepository,
    FakeStorage,
    FakeIngestion,
    FakeRag,
    FakeInterpreter,
]:
    analyses = FakeAnalysisRepository()
    events = FakeEventRepository()
    storage = FakeStorage()
    ingestion = FakeIngestion(text, delay=ingestion_delay)
    rag_client = rag or FakeRag(_rag_result())
    interpreter_client = interpreter or FakeInterpreter()
    orchestrator = LangGraphAnalysisOrchestrator(
        ingestion=ingestion,
        fraud_service=FraudScoringService(model=model),
        retriever=rag_client,
        interpreter=interpreter_client,
        analyses=analyses,
        events=events,
        storage=storage,
        settings=settings or _settings(),
        regulatory=regulatory,
        clock=lambda: _NOW,
        cancellation=cancellation,
        judge=judge,
        tracer=observability,
    )
    return (
        orchestrator,
        analyses,
        events,
        storage,
        ingestion,
        rag_client,
        interpreter_client,
    )


async def _run(
    orchestrator: LangGraphAnalysisOrchestrator,
    *,
    kind: DocumentKind = DocumentKind.BANK_SLIP,
    analysis_id: UUID | None = None,
) -> Any:
    return await orchestrator.run(
        analysis_id=analysis_id or uuid4(),
        document=_document(kind),
        data=b"data",
        locale="pt",
    )


async def test_boleto_runs_end_to_end_with_fake_llm() -> None:
    boleto = build_boleto()
    orchestrator, analyses, _events, storage, _, rag_client, interpreter = _orchestrator(
        boleto.ocr_text(),
        model=FakeModel(),
    )

    report = await _run(orchestrator)

    assert report.document_type is AnalysisDocumentType.BOLETO
    assert report.score >= 0
    assert report.evidence == ()
    assert analyses.completed is not None
    assert analyses.completed["score"] == report.score
    assert storage.puts
    assert storage.puts[0]["key"].endswith("/report.json")
    assert storage.puts[0]["content_type"] == "application/json"
    payload = json.loads(storage.puts[0]["data"])
    assert payload["document_type"] == "boleto"
    assert payload["score"] == report.score
    assert payload["model_versions"]["ml"] == "fake-ml"
    assert payload["model_versions"]["llm"] == "fake-llm"
    assert payload["model_versions"]["prompt"] == "p11-test"
    assert rag_client.query is not None
    assert interpreter.request is not None
    assert "Trecho de conhecimento." in interpreter.request.rag_snippets
    assert analyses.completed is not None
    completed = analyses.completed["event"]
    assert isinstance(completed, AnalysisEvent)
    assert completed.event_type is AnalysisEventType.COMPLETED
    notifications = analyses.completed["notifications"]
    assert len(notifications) == 1
    assert notifications[0].payload["status"] == "completed"
    assert notifications[0].type is NotificationType.ANALYSIS_COMPLETED


async def test_progress_is_monotonic_and_reaches_one_hundred() -> None:
    boleto = build_boleto()
    orchestrator, analyses, _events, _storage, _ingestion, _rag, _interpreter = _orchestrator(
        boleto.ocr_text(),
        model=FakeModel(),
    )

    await _run(orchestrator)

    percents = [item["percent"] for item in analyses.progress]
    stages = [item["stage"] for item in analyses.progress]
    assert percents == sorted(percents)
    assert percents[-1] == 100
    assert set(stages) == set(AnalysisStage)
    assert any(
        item["stage"] is AnalysisStage.OCR and item["detail"] == "Página 1 de 1"
        for item in analyses.progress
    )
    assert all(
        isinstance(item["event"], AnalysisEvent)
        and item["event"].event_type is AnalysisEventType.PROGRESS
        for item in analyses.progress
    )


async def test_cancelled_before_first_stage_aborts_without_completing() -> None:
    boleto = build_boleto()
    cancellation = FakeCancellation(cancelled=True)
    orchestrator, analyses, _events, _storage, _ingestion, _rag, _interpreter = _orchestrator(
        boleto.ocr_text(),
        model=FakeModel(),
        cancellation=cancellation,
    )

    with pytest.raises(AnalysisCancelledError):
        await _run(orchestrator)

    assert analyses.completed is None
    assert analyses.failed is None
    assert analyses.progress == []


async def test_payslip_runs_with_synthetic_regulatory_tables() -> None:
    orchestrator, _, _, storage, _, _, _ = _orchestrator(
        SyntheticPayslip().ocr_text(),
        kind=DocumentKind.PAYSLIP,
        model=FakeModel(),
        regulatory=synthetic_regulatory_tables(),
    )

    report = await _run(orchestrator, kind=DocumentKind.PAYSLIP)

    assert report.document_type is AnalysisDocumentType.PAYSLIP
    assert report.fields["employee_cpf_masked"] == "***.***.***-09"
    assert "12345678909" not in json.dumps(report.to_dict())
    assert json.loads(storage.puts[0]["data"])["document_type"] == "payslip"


async def test_tampered_boleto_score_is_reproducible_from_events() -> None:
    boleto = build_boleto()
    tampered = boleto.line[:9] + str((int(boleto.line[9]) + 1) % 10) + boleto.line[10:]
    text = boleto.ocr_text().replace(boleto.formatted_line, format_line(tampered))
    orchestrator, analyses, events, _, _, _, _ = _orchestrator(
        text,
        model=FakeModel(),
    )

    report = await _run(orchestrator)

    rule_events = [
        event for event in events.events if event.event_type is AnalysisEventType.RULE_TRIGGERED
    ]
    assert analyses.completed is not None
    completed = analyses.completed["event"]
    assert isinstance(completed, AnalysisEvent)
    assert rule_events
    weights = sum(int(event.payload["weight"]) for event in rule_events)
    critical = any(event.payload["severity"] == "critical" for event in rule_events)
    deterministic = max(80, weights) if critical else weights
    assert deterministic == int(completed.payload["deterministic_score"])
    config = ScoringConfig()
    ml_probability = (
        float(completed.payload["ml_probability"]) if completed.payload["ml_probability"] else None
    )
    anomaly = (
        float(completed.payload["anomaly_score"]) if completed.payload["anomaly_score"] else None
    )
    fused = fuse_risk(
        deterministic_score=deterministic,
        critical_present=critical,
        ml_probability=ml_probability,
        anomaly_score=anomaly,
        visual_score=float(completed.payload["visual_score"]),
        config=config,
    )
    assert fused.score == int(completed.payload["base_score"])
    final = min(100, fused.score + int(completed.payload["llm_adjustment"]))
    if critical:
        final = max(final, config.critical_floor)
    assert final == report.score
    assert final == int(completed.payload["score"])


async def test_event_payloads_have_no_personal_data_or_document_text() -> None:
    boleto = build_boleto()
    orchestrator, _, events, _, _, _, _ = _orchestrator(
        boleto.ocr_text(),
        model=FakeModel(),
    )

    await _run(orchestrator)

    serialized = json.dumps([event.payload for event in events.events])
    assert "PAGAMENTOS SINTETICOS" not in serialized
    assert "123.456.789-09" not in serialized
    assert "12345678909" not in serialized
    assert "@" not in serialized
    assert "CONTEUDO" not in serialized


async def test_ml_degradation_is_flagged() -> None:
    orchestrator, _, events, _, _, _, _ = _orchestrator(
        build_boleto().ocr_text(),
        model=None,
    )

    report = await _run(orchestrator)

    assert DegradationFlag.ML_UNAVAILABLE in report.degradation_flags
    assert any(
        event.event_type is AnalysisEventType.DEGRADED
        and event.degradation_flags == (DegradationFlag.ML_UNAVAILABLE,)
        for event in events.events
    )


async def test_rag_degradation_is_flagged() -> None:
    orchestrator, _, events, _, _, _, interpreter = _orchestrator(
        build_boleto().ocr_text(),
        model=FakeModel(),
        rag=FakeRag(_rag_result(unavailable=True)),
    )

    report = await _run(orchestrator)

    assert DegradationFlag.RAG_UNAVAILABLE in report.degradation_flags
    assert interpreter.request is not None
    assert interpreter.request.rag_snippets == ()
    assert any(
        event.event_type is AnalysisEventType.DEGRADED
        and event.degradation_flags == (DegradationFlag.RAG_UNAVAILABLE,)
        for event in events.events
    )


async def test_llm_degradation_is_flagged_and_does_not_change_base_score() -> None:
    orchestrator, _, events, _, _, _, _ = _orchestrator(
        build_boleto().ocr_text(),
        model=FakeModel(),
        interpreter=FakeInterpreter(error=LlmUnavailableError("offline")),
    )

    report = await _run(orchestrator)

    assert DegradationFlag.LLM_UNAVAILABLE in report.degradation_flags
    assert report.llm_adjustment == 0
    assert report.score == report.base_score
    assert report.justification
    assert any(
        event.event_type is AnalysisEventType.DEGRADED
        and event.degradation_flags == (DegradationFlag.LLM_UNAVAILABLE,)
        for event in events.events
    )


async def test_ingest_timeout_fails_the_analysis() -> None:
    orchestrator, _, _, _, _, _, _ = _orchestrator(
        build_boleto().ocr_text(),
        model=FakeModel(),
        settings=_settings(node_timeout=0.01),
        ingestion_delay=0.05,
    )

    with pytest.raises(AnalysisTimeoutError):
        await _run(orchestrator)


async def test_trace_contains_pipeline_spans_and_scores_without_pii() -> None:
    boleto = build_boleto()
    observability = FakeObservability()
    settings = _settings().model_copy(update={"guardrail_judge_enabled": True})
    orchestrator, *_ = _orchestrator(
        boleto.ocr_text(),
        model=FakeModel(),
        settings=settings,
        judge=FakeJudge(),
        observability=observability,
    )
    analysis_id = uuid4()

    report = await _run(orchestrator, analysis_id=analysis_id)

    names = [span["name"] for span in observability.spans]
    assert {
        "ocr",
        "classifier.document",
        "guardrail.input",
        "retrieval",
        "classifier.risk",
        "guardrail.output",
        "guardrail.judge",
    } <= set(names)
    assert observability.traces[0]["name"] == "analysis"
    assert observability.traces[0]["session_id"] == str(analysis_id)
    assert observability.traces[0]["environment"] == "local"
    assert "env:local" in observability.traces[0]["tags"]
    score_names = {score["name"] for score in observability.scores}
    assert {
        "risk_score",
        "risk_band",
        "rerank_alterou_top1",
        "guardrail_failed",
        "judge_approved",
        "judge_verdict",
    } <= score_names
    assert report.score >= 0
    serialized = json.dumps(
        {
            "traces": observability.traces,
            "spans": observability.spans,
            "updates": observability.updates,
            "scores": observability.scores,
        },
        default=str,
    )
    assert "123.456.789-09" not in serialized
    assert "12345678909" not in serialized
    assert "PAGAMENTOS SINTETICOS" not in serialized
    assert "CONTEUDO" not in serialized


async def test_langfuse_disabled_pipeline_matches_default_result() -> None:
    from paysentineliq.infrastructure.observability.langfuse_tracer import (
        build_observability_tracer,
    )
    from paysentineliq.infrastructure.observability.noop_tracer import NoopTracer

    boleto = build_boleto()
    default, *_ = _orchestrator(boleto.ocr_text(), model=FakeModel())
    disabled_tracer = build_observability_tracer(_settings())
    assert isinstance(disabled_tracer, NoopTracer)
    with_noop, *_ = _orchestrator(
        boleto.ocr_text(),
        model=FakeModel(),
        observability=disabled_tracer,
    )

    first = await _run(default)
    second = await _run(with_noop)

    assert first.score == second.score
    assert first.band == second.band
    assert first.fields == second.fields
    assert first.evidence == second.evidence
    assert first.justification == second.justification
    assert first.inconsistencies == second.inconsistencies
    assert first.degradation_flags == second.degradation_flags
