from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol
from uuid import UUID

from paysentineliq.domain.payables import (
    Payable,
    PayableStatus,
    ReminderPreference,
)


@dataclass(frozen=True, slots=True)
class PayableTransitionResult:
    payable: Payable | None
    outcome: Literal["updated", "unchanged", "not_found", "invalid_state"]


@dataclass(frozen=True, slots=True)
class ReminderDispatchResult:
    created: int = 0
    notification_ids: tuple[UUID, ...] = ()


class PayableReadRepositoryPort(Protocol):
    async def get_for_owner(
        self,
        payable_id: UUID,
        owner_id: UUID,
    ) -> Payable | None: ...

    async def list_for_owner(
        self,
        owner_id: UUID,
        *,
        statuses: tuple[PayableStatus, ...] = (),
        due_from: date | None = None,
        due_to: date | None = None,
        limit: int,
        before: tuple[date, UUID] | None = None,
    ) -> tuple[Payable, ...]: ...


class PayableWriteRepositoryPort(Protocol):
    async def confirm(
        self,
        payable_id: UUID,
        owner_id: UUID,
    ) -> PayableTransitionResult: ...

    async def pay(
        self,
        payable_id: UUID,
        owner_id: UUID,
    ) -> PayableTransitionResult: ...

    async def dismiss(
        self,
        payable_id: UUID,
        owner_id: UUID,
    ) -> PayableTransitionResult: ...

    async def reschedule(
        self,
        payable_id: UUID,
        owner_id: UUID,
        due_date: date,
    ) -> PayableTransitionResult: ...


class ReminderPreferenceRepositoryPort(Protocol):
    async def get_for_user(self, user_id: UUID) -> ReminderPreference: ...

    async def upsert(self, preference: ReminderPreference) -> ReminderPreference: ...


class PayableReminderRepositoryPort(Protocol):
    async def create_due_reminders(
        self,
        now: datetime,
        *,
        lookback_days: int,
    ) -> ReminderDispatchResult: ...

    async def mark_overdue(self, now: datetime) -> ReminderDispatchResult: ...
