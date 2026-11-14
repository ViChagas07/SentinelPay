import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from paysentineliq.application.commands.process_analysis import (
    ProcessAnalysisHandler,
    analysis_error_code,
    is_retryable_analysis_error,
)
from paysentineliq.application.errors import DocumentNotFoundError, UnsupportedDocumentError
from paysentineliq.application.ports.analysis import AnalysisDocument
from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisEvent,
    AnalysisRecord,
    AnalysisReport,
    AnalysisStatus,
    DegradationFlag,
)
from paysentineliq.domain.document import DocumentKind
from paysentineliq.domain.notification import Notification, NotificationType
from paysentineliq.domain.scoring import RiskBand

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_DOCUMENT = AnalysisDocument(
    id=uuid4(),
    owner_id=uuid4(),
    kind=DocumentKind.BANK_SLIP,
    s3_key="users/owner/bank_slip/analysis/original.pdf",
    content_type="application/pdf",
    size=10,
)


class FakeSource:
    def __init__(self, *, missing: bool = False, read_error: Exception | None = None) -> None:
        self._missing = missing
        self._read_error = read_error

    async def get(self, document_id: UUID) -> AnalysisDocument | None:
        return None if self._missing else _DOCUMENT

    async def read(self, document: AnalysisDocument) -> bytes:
        if self._read_error is not None:
            raise self._read_error
        return b"data"


class FakeOrchestrator:
    def __init__(self, *, error: Exception | None = None) -> None:
        self._error = error
        self.calls = 0

    async def run(
        self,
        *,
        analysis_id: UUID,
        document: AnalysisDocument,
        data: bytes,
        locale: str = "pt",
    ) -> AnalysisReport:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return AnalysisReport(
            analysis_id=analysis_id,
            document_id=document.id,
            document_type=AnalysisDocumentType.BOLETO,
            score=80,
            band=RiskBand.HIGH,
            base_score=80,
            llm_adjustment=0,
            fields={},
            evidence=(),
            justification="ok",
            inconsistencies=(),
            rule_set_version="test",
            model_versions={},
            degradation_flags=(),
            report_s3_key="report.json",
            created_at=_NOW,
        )


class FakeAnalyses:
    def __init__(self, *, claim: bool = True) -> None:
        self._claim = claim
        self.claims: list[dict[str, object]] = []
        self.requeued: list[dict[str, object]] = []
        self.failed: list[dict[str, object]] = []

    async def claim_for_processing(
        self,
        analysis_id: UUID,
        *,
        task_id: str,
        lease_seconds: int,
        event: AnalysisEvent | None = None,
    ) -> AnalysisRecord | None:
        self.claims.append({"task_id": task_id, "lease": lease_seconds, "event": event})
        if not self._claim:
            return None
        return AnalysisRecord(
            id=analysis_id,
            owner_id=_DOCUMENT.owner_id,
            document_id=_DOCUMENT.id,
            document_type=AnalysisDocumentType.BOLETO,
            status=AnalysisStatus.PROCESSING,
            score=None,
            band=None,
            rule_set_version=None,
            model_versions={},
            degradation_flags=(),
            state={},
            report_s3_key=None,
            error_code=None,
            created_at=_NOW,
            updated_at=_NOW,
        )

    async def requeue_for_retry(
        self,
        analysis_id: UUID,
        *,
        error_code: str,
        state: Mapping[str, object],
        event: AnalysisEvent,
    ) -> bool:
        self.requeued.append({"error_code": error_code, "event": event})
        return True

    async def fail(
        self,
        analysis_id: UUID,
        *,
        error_code: str,
        state: Mapping[str, object],
        event: AnalysisEvent | None = None,
        notifications: tuple[Notification, ...] = (),
    ) -> bool:
        self.failed.append({"error_code": error_code, "event": event})
        return True

    async def create(
        self,
        record: AnalysisRecord,
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
        notifications: tuple[Notification, ...] = (),
    ) -> bool:
        return True

    async def get(self, analysis_id: UUID) -> AnalysisRecord | None:
        return None

    async def find_by_idempotency(self, owner_id: UUID, idempotency_key: str) -> None:
        return None

    async def count_active_for_owner(self, owner_id: UUID) -> int:
        return 0

    async def list_stale_processing(self, before: datetime) -> tuple[AnalysisRecord, ...]:
        return ()


class FakeNotifications:
    def __init__(self, notification_id: UUID | None = None) -> None:
        self._notification_id = notification_id

    async def list_pending_for_analysis(
        self,
        analysis_id: UUID,
    ) -> tuple[Notification, ...]:
        if self._notification_id is None:
            return ()
        return (
            Notification(
                id=self._notification_id,
                owner_id=_DOCUMENT.owner_id,
                analysis_id=analysis_id,
                type=NotificationType.ANALYSIS_COMPLETED,
                payload={"status": "completed"},
            ),
        )

    async def mark_dispatched(self, notification_id: UUID) -> None:
        return None


def _handler(
    *,
    analyses: FakeAnalyses | None = None,
    source: FakeSource | None = None,
    orchestrator: FakeOrchestrator | None = None,
    notification_id: UUID | None = None,
) -> tuple[ProcessAnalysisHandler, FakeAnalyses, FakeOrchestrator]:
    fake_analyses = analyses or FakeAnalyses()
    fake_orchestrator = orchestrator or FakeOrchestrator()
    return (
        ProcessAnalysisHandler(
            source or FakeSource(),
            fake_orchestrator,
            fake_analyses,
            FakeNotifications(notification_id),
            lease_seconds=300,
        ),
        fake_analyses,
        fake_orchestrator,
    )


async def test_success_claims_runs_and_returns_notification_ids() -> None:
    notification_id = uuid4()
    handler, analyses, orchestrator = _handler(notification_id=notification_id)

    result = await handler.execute(
        uuid4(),
        task_id="task-1",
        attempt=1,
        final_attempt=False,
    )

    assert result.status == "completed"
    assert result.notification_ids == (notification_id,)
    assert orchestrator.calls == 1
    assert analyses.claims[0]["task_id"] == "task-1"
    assert analyses.requeued == []
    assert analyses.failed == []


async def test_duplicate_delivery_skips_without_running() -> None:
    handler, _analyses, orchestrator = _handler(analyses=FakeAnalyses(claim=False))

    result = await handler.execute(
        uuid4(),
        task_id="task-2",
        attempt=1,
        final_attempt=False,
    )

    assert result.status == "skipped"
    assert orchestrator.calls == 0


async def test_retryable_failure_requeues_when_not_final() -> None:
    handler, analyses, _ = _handler(
        orchestrator=FakeOrchestrator(error=RuntimeError("db blip")),
    )

    with pytest.raises(RuntimeError):
        await handler.execute(
            uuid4(),
            task_id="task-3",
            attempt=1,
            final_attempt=False,
        )

    assert analyses.requeued
    assert analyses.requeued[0]["error_code"] == "analysis_failed"
    assert analyses.failed == []


async def test_retryable_failure_marks_failed_on_final_attempt() -> None:
    handler, analyses, _ = _handler(
        orchestrator=FakeOrchestrator(error=RuntimeError("db blip")),
    )

    with pytest.raises(RuntimeError):
        await handler.execute(
            uuid4(),
            task_id="task-4",
            attempt=3,
            final_attempt=True,
        )

    assert analyses.requeued == []
    assert analyses.failed[0]["error_code"] == "analysis_failed"


async def test_non_retryable_failure_marks_failed_immediately() -> None:
    handler, analyses, _ = _handler(
        orchestrator=FakeOrchestrator(error=UnsupportedDocumentError()),
    )

    with pytest.raises(UnsupportedDocumentError):
        await handler.execute(
            uuid4(),
            task_id="task-5",
            attempt=1,
            final_attempt=False,
        )

    assert analyses.requeued == []
    assert analyses.failed[0]["error_code"] == "unsupported_document"
    assert is_retryable_analysis_error(UnsupportedDocumentError()) is False


async def test_missing_document_fails_safe() -> None:
    handler, analyses, _ = _handler(source=FakeSource(missing=True))

    with pytest.raises(DocumentNotFoundError):
        await handler.execute(
            uuid4(),
            task_id="task-6",
            attempt=1,
            final_attempt=False,
        )

    assert analyses.failed[0]["error_code"] == "document_not_found"


def test_error_codes_are_safe_and_bounded() -> None:
    assert analysis_error_code(RuntimeError("secret detail")) == "analysis_failed"
    assert len(analysis_error_code(RuntimeError("x" * 1000))) <= 64


def test_run_async_uses_a_dedicated_loop_each_time() -> None:
    from paysentineliq.infrastructure.messaging.async_bridge import run_async

    async def value() -> int:
        return 7

    assert run_async(value) == 7
    assert run_async(value) == 7
    with pytest.raises(RuntimeError):
        asyncio.get_event_loop_policy().get_event_loop()
