from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from paysentineliq.domain.payables import NotificationChannel


class NotificationType(StrEnum):
    ANALYSIS_COMPLETED = "analysis_completed"
    PAYABLE_DUE_REMINDER = "payable_due_reminder"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Notification:
    id: UUID
    owner_id: UUID
    analysis_id: UUID
    type: NotificationType
    payload: Mapping[str, str] = field(default_factory=dict)
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime | None = None
    channel: NotificationChannel = NotificationChannel.IN_APP
    payable_id: UUID | None = None
    reminder_due_date: date | None = None
    reminder_offset_days: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("notification id must be a UUID")
        if not isinstance(self.owner_id, UUID):
            raise ValueError("owner_id must be a UUID")
        if not isinstance(self.analysis_id, UUID):
            raise ValueError("analysis_id must be a UUID")
        if len(self.payload) > 10:
            raise ValueError("notification payload is too large")
        for key, value in self.payload.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("notification payload must contain string keys and values")
            if len(key) > 64 or len(value) > 512:
                raise ValueError("notification payload item is too large")
        if self.reminder_offset_days is not None and not 0 <= self.reminder_offset_days <= 30:
            raise ValueError("reminder_offset_days must be between 0 and 30")
        if (self.reminder_due_date is None) != (self.reminder_offset_days is None):
            raise ValueError("reminder due date and offset must be provided together")
