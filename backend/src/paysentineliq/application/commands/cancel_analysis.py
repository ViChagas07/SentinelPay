import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from paysentineliq.application.errors import (
    AnalysisNotCancellableError,
    AnalysisNotFoundError,
)
from paysentineliq.application.ports.analysis_cancellation import (
    AnalysisCancellationRepositoryPort,
    CancelOutcome,
)
from paysentineliq.application.ports.cancellation import CancellationPort
from paysentineliq.application.ports.storage import StoragePort
from paysentineliq.application.ports.task_dispatcher import TaskDispatcherPort
from paysentineliq.application.security.storage_keys import build_analysis_report_key
from paysentineliq.domain.analysis import AnalysisEvent, AnalysisEventType, AnalysisStatus

_logger = logging.getLogger("paysentineliq")


@dataclass(frozen=True, slots=True)
class AnalysisCancellationDTO:
    analysis_id: UUID
    status: AnalysisStatus


class CancelAnalysisHandler:
    def __init__(
        self,
        repository: AnalysisCancellationRepositoryPort,
        cancellation: CancellationPort,
        dispatcher: TaskDispatcherPort,
        storage: StoragePort | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._cancellation = cancellation
        self._dispatcher = dispatcher
        self._storage = storage
        self._clock = clock or (lambda: datetime.now(UTC))

    async def handle(self, analysis_id: UUID, owner_id: UUID) -> AnalysisCancellationDTO:
        now = self._clock()
        transition = await self._repository.request_cancel(
            analysis_id,
            owner_id,
            now=now,
            event=AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.CANCELLING,
                payload={"stage": "cancel"},
            ),
        )
        record = transition.record
        if transition.outcome is CancelOutcome.NOT_FOUND:
            raise AnalysisNotFoundError()
        if transition.outcome is CancelOutcome.NOT_CANCELLABLE:
            raise AnalysisNotCancellableError()
        if transition.outcome is CancelOutcome.REQUESTED:
            await self._cancellation.request(analysis_id)
            if record is not None and record.task_id:
                try:
                    self._dispatcher.revoke_analysis(record.task_id)
                except Exception:
                    _logger.warning("analysis_task_revoke_failed")
            return AnalysisCancellationDTO(
                analysis_id=analysis_id,
                status=AnalysisStatus.CANCELLING,
            )
        if record is not None and record.status is AnalysisStatus.CANCELLING:
            await self._cancellation.request(analysis_id)
            return AnalysisCancellationDTO(
                analysis_id=analysis_id,
                status=AnalysisStatus.CANCELLING,
            )
        await self._cancellation.clear(analysis_id)
        if record is not None:
            await self._delete_partial_report(record.owner_id, analysis_id)
        return AnalysisCancellationDTO(
            analysis_id=analysis_id,
            status=AnalysisStatus.CANCELLED,
        )

    async def _delete_partial_report(self, owner_id: UUID, analysis_id: UUID) -> None:
        if self._storage is None:
            return
        key = build_analysis_report_key(owner_id=owner_id, analysis_id=analysis_id)
        try:
            await self._storage.delete(key)
        except Exception:
            _logger.warning("analysis_partial_report_delete_failed")
