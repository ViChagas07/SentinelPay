from datetime import date, time
from uuid import UUID

from paysentineliq.application.errors import (
    PayableNotFoundError,
    PayableStateError,
)
from paysentineliq.application.ports.payables import (
    PayableTransitionResult,
    PayableWriteRepositoryPort,
    ReminderPreferenceRepositoryPort,
)
from paysentineliq.domain.payables import (
    NotificationChannel,
    Payable,
    ReminderPreference,
)


class PayableCommandHandler:
    def __init__(self, repository: PayableWriteRepositoryPort) -> None:
        self._repository = repository

    async def confirm(self, payable_id: UUID, owner_id: UUID) -> Payable:
        return _resolve(await self._repository.confirm(payable_id, owner_id))

    async def pay(self, payable_id: UUID, owner_id: UUID) -> Payable:
        return _resolve(await self._repository.pay(payable_id, owner_id))

    async def dismiss(self, payable_id: UUID, owner_id: UUID) -> Payable:
        return _resolve(await self._repository.dismiss(payable_id, owner_id))

    async def reschedule(
        self,
        payable_id: UUID,
        owner_id: UUID,
        due_date: date,
    ) -> Payable:
        return _resolve(
            await self._repository.reschedule(payable_id, owner_id, due_date),
        )


class ReminderPreferenceHandler:
    def __init__(self, repository: ReminderPreferenceRepositoryPort) -> None:
        self._repository = repository

    async def get(self, user_id: UUID) -> ReminderPreference:
        return await self._repository.get_for_user(user_id)

    async def update(
        self,
        user_id: UUID,
        *,
        offsets_days: tuple[int, ...],
        local_time: time,
        channels: tuple[NotificationChannel, ...],
    ) -> ReminderPreference:
        preference = ReminderPreference(
            user_id=user_id,
            offsets_days=offsets_days,
            local_time=local_time,
            channels=channels,
        )
        return await self._repository.upsert(preference)


def _resolve(result: PayableTransitionResult) -> Payable:
    if result.outcome == "not_found" or result.payable is None:
        raise PayableNotFoundError()
    if result.outcome == "invalid_state":
        raise PayableStateError()
    return result.payable
