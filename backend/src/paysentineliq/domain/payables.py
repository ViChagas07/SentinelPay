from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID

from paysentineliq.domain.scoring import RiskBand


class PayableStatus(StrEnum):
    PENDING_CONFIRMATION = "pending_confirmation"
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    DISMISSED = "dismissed"


class NotificationChannel(StrEnum):
    IN_APP = "in_app"


DEFAULT_OFFSETS = (3, 1, 0)
DEFAULT_LOCAL_TIME = time(9, 0)
DEFAULT_CHANNELS = (NotificationChannel.IN_APP,)


@dataclass(frozen=True, slots=True)
class Payable:
    id: UUID
    owner_id: UUID
    analysis_id: UUID
    description: str
    amount_cents: int
    due_date: date
    status: PayableStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        description = " ".join(self.description.split())
        if not description:
            raise ValueError("description is required")
        if len(description) > 200:
            raise ValueError("description is too long")
        object.__setattr__(self, "description", description)
        if self.amount_cents <= 0:
            raise ValueError("amount_cents must be positive")


@dataclass(frozen=True, slots=True)
class ReminderPreference:
    user_id: UUID
    offsets_days: tuple[int, ...] = DEFAULT_OFFSETS
    local_time: time = DEFAULT_LOCAL_TIME
    channels: tuple[NotificationChannel, ...] = DEFAULT_CHANNELS
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.offsets_days:
            raise ValueError("at least one offset is required")
        if len(set(self.offsets_days)) != len(self.offsets_days):
            raise ValueError("offsets must be unique")
        if any(not 0 <= offset <= 30 for offset in self.offsets_days):
            raise ValueError("offsets must be between 0 and 30")
        if not self.channels:
            raise ValueError("at least one channel is required")
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("channels must be unique")

    @property
    def sorted_offsets(self) -> tuple[int, ...]:
        return tuple(sorted(self.offsets_days, reverse=True))


def payable_status_for(
    band: RiskBand,
    *,
    injection_detected: bool = False,
) -> PayableStatus | None:
    if band is RiskBand.HIGH:
        return None
    if band is RiskBand.ATTENTION or injection_detected:
        return PayableStatus.PENDING_CONFIRMATION
    return PayableStatus.PENDING


TERMINAL_STATUSES = frozenset(
    {PayableStatus.PAID, PayableStatus.DISMISSED},
)
ACTIVE_STATUSES = frozenset(
    {
        PayableStatus.PENDING_CONFIRMATION,
        PayableStatus.PENDING,
        PayableStatus.OVERDUE,
    },
)


@dataclass(frozen=True, slots=True)
class PayableListFilter:
    statuses: tuple[PayableStatus, ...] = ()
    due_from: date | None = None
    due_to: date | None = None


@dataclass(frozen=True, slots=True)
class PayablePage:
    items: tuple[Payable, ...] = field(default_factory=tuple)
    next_cursor: str | None = None
