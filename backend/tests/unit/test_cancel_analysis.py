from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from paysentineliq.application.commands.cancel_analysis import CancelAnalysisHandler
from paysentineliq.application.errors import (
    AnalysisNotCancellableError,
    AnalysisNotFoundError,
)
from paysentineliq.application.ports.analysis_cancellation import (
    CancelOutcome,
    CancelTransition,
)
from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisEvent,
    AnalysisRecord,
    AnalysisStatus,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_OWNER = uuid4()


def _record(
    *,
    status: AnalysisStatus = AnalysisStatus.RUNNING,
    task_id: str | None = "task-1",
) -> AnalysisRecord:
    return AnalysisRecord(
        id=uuid4(),
        owner_id=_OWNER,
        document_id=uuid4(),
        document_type=AnalysisDocumentType.BOLETO,
        status=status,
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
        task_id=task_id,
    )


class FakeRepository:
    def __init__(self, transition: CancelTransition) -> None:
        self.transition = transition
        self.finalized: list[UUID] = []

    async def request_cancel(
        self,
        analysis_id: UUID,
        owner_id: UUID,
        *,
        now: datetime,
        event: AnalysisEvent | None = None,
    ) -> CancelTransition:
        return self.transition

    async def finalize_cancelled(
        self,
        analysis_id: UUID,
        *,
        event: AnalysisEvent | None = None,
    ) -> bool:
        self.finalized.append(analysis_id)
        return True

    async def list_stale_cancelling(self, before: datetime) -> tuple[AnalysisRecord, ...]:
        return ()


class FakeCancellation:
    def __init__(self) -> None:
        self.requested: list[UUID] = []
        self.cleared: list[UUID] = []

    async def request(self, analysis_id: UUID) -> None:
        self.requested.append(analysis_id)

    async def clear(self, analysis_id: UUID) -> None:
        self.cleared.append(analysis_id)

    async def is_cancelled(self, analysis_id: UUID) -> bool:
        return analysis_id in self.requested and analysis_id not in self.cleared


class FakeDispatcher:
    def __init__(self) -> None:
        self.revoked: list[str] = []

    def dispatch_analysis(self, analysis_id: UUID, *, locale: str = "pt") -> None:
        return None

    def dispatch_notification(self, notification_id: UUID) -> None:
        return None

    def revoke_analysis(self, task_id: str) -> None:
        self.revoked.append(task_id)


class FakeStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def delete(self, key: str) -> None:
        self.deleted.append(key)

    async def put(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def get_stream(self, key: str) -> Any:
        yield b""

    async def presigned_get_url(self, key: str, *, expires_in: int) -> str:
        return key


def _handler(
    transition: CancelTransition,
) -> tuple[CancelAnalysisHandler, FakeRepository, FakeCancellation, FakeDispatcher, FakeStorage]:
    repository = FakeRepository(transition)
    cancellation = FakeCancellation()
    dispatcher = FakeDispatcher()
    storage = FakeStorage()
    return (
        CancelAnalysisHandler(
            repository,
            cancellation,
            dispatcher,
            storage,
            clock=lambda: _NOW,
        ),
        repository,
        cancellation,
        dispatcher,
        storage,
    )


async def test_running_analysis_requests_cooperative_cancel_and_revokes_task() -> None:
    record = _record(status=AnalysisStatus.RUNNING, task_id="task-42")
    handler, _repo, cancellation, dispatcher, storage = _handler(
        CancelTransition(outcome=CancelOutcome.REQUESTED, record=record),
    )

    result = await handler.handle(record.id, _OWNER)

    assert result.status is AnalysisStatus.CANCELLING
    assert cancellation.requested == [record.id]
    assert cancellation.cleared == []
    assert dispatcher.revoked == ["task-42"]
    assert storage.deleted == []


async def test_queued_analysis_is_cancelled_immediately_and_removes_partial_report() -> None:
    record = _record(status=AnalysisStatus.CANCELLED, task_id=None)
    handler, _repo, cancellation, dispatcher, storage = _handler(
        CancelTransition(outcome=CancelOutcome.CANCELLED, record=record),
    )

    result = await handler.handle(record.id, _OWNER)

    assert result.status is AnalysisStatus.CANCELLED
    assert cancellation.requested == []
    assert cancellation.cleared == [record.id]
    assert dispatcher.revoked == []
    assert storage.deleted
    assert str(record.id) in storage.deleted[0]


async def test_completed_analysis_is_not_cancellable() -> None:
    record = _record(status=AnalysisStatus.COMPLETED)
    handler, _repo, cancellation, dispatcher, storage = _handler(
        CancelTransition(outcome=CancelOutcome.NOT_CANCELLABLE, record=record),
    )

    with pytest.raises(AnalysisNotCancellableError):
        await handler.handle(record.id, _OWNER)

    assert cancellation.requested == []
    assert dispatcher.revoked == []
    assert storage.deleted == []


async def test_missing_analysis_is_not_found() -> None:
    handler, _repo, _cancellation, _dispatcher, _storage = _handler(
        CancelTransition(outcome=CancelOutcome.NOT_FOUND),
    )

    with pytest.raises(AnalysisNotFoundError):
        await handler.handle(uuid4(), _OWNER)


async def test_repeated_cancel_while_cancelling_keeps_the_flag() -> None:
    record = _record(status=AnalysisStatus.CANCELLING)
    handler, _repo, cancellation, dispatcher, storage = _handler(
        CancelTransition(outcome=CancelOutcome.ALREADY_CANCELLED, record=record),
    )

    result = await handler.handle(record.id, _OWNER)

    assert result.status is AnalysisStatus.CANCELLING
    assert cancellation.cleared == []
    assert cancellation.requested == [record.id]
    assert dispatcher.revoked == []
    assert storage.deleted == []


async def test_repeated_cancel_after_cancelled_is_idempotent() -> None:
    record = _record(status=AnalysisStatus.CANCELLED)
    handler, _repo, cancellation, _dispatcher, storage = _handler(
        CancelTransition(outcome=CancelOutcome.ALREADY_CANCELLED, record=record),
    )

    result = await handler.handle(record.id, _OWNER)

    assert result.status is AnalysisStatus.CANCELLED
    assert cancellation.cleared == [record.id]
    assert storage.deleted
