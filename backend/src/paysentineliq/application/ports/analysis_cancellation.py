from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from paysentineliq.domain.analysis import AnalysisEvent, AnalysisRecord


class CancelOutcome(StrEnum):
    REQUESTED = "requested"
    CANCELLED = "cancelled"
    ALREADY_CANCELLED = "already_cancelled"
    NOT_CANCELLABLE = "not_cancellable"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class CancelTransition:
    outcome: CancelOutcome
    record: AnalysisRecord | None = None


class AnalysisCancellationRepositoryPort(Protocol):
    async def request_cancel(
        self,
        analysis_id: UUID,
        owner_id: UUID,
        *,
        now: datetime,
        event: AnalysisEvent | None = None,
    ) -> CancelTransition: ...

    async def finalize_cancelled(
        self,
        analysis_id: UUID,
        *,
        event: AnalysisEvent | None = None,
    ) -> bool: ...

    async def list_stale_cancelling(
        self,
        before: datetime,
    ) -> tuple[AnalysisRecord, ...]: ...
