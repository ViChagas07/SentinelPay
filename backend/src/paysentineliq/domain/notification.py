import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from paysentineliq.domain.payables import NotificationChannel

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_e164(value: str) -> bool:
    return _E164.fullmatch(value) is not None


def is_email(value: str) -> bool:
    return _EMAIL.fullmatch(value) is not None


class NotificationType(StrEnum):
    ANALYSIS_COMPLETED = "analysis_completed"
    HIGH_RISK_DETECTED = "high_risk_detected"
    RECEIPT_ANALYZED = "receipt_analyzed"
    PAYABLE_DUE_SOON = "payable_due_soon"
    PAYABLE_DUE_TODAY = "payable_due_today"
    PAYABLE_OVERDUE = "payable_overdue"
    PAYABLE_DUE_REMINDER = "payable_due_reminder"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryChannel(StrEnum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class Notification:
    id: UUID
    owner_id: UUID
    analysis_id: UUID
    type: NotificationType
    payload: Mapping[str, str] = field(default_factory=dict)
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime | None = None
    read_at: datetime | None = None
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

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


@dataclass(frozen=True, slots=True)
class NotificationPreference:
    channel: DeliveryChannel
    enabled: bool = False
    destination: str | None = None
    consented_at: datetime | None = None
    user_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        destination = self.destination.strip() if self.destination is not None else None
        object.__setattr__(self, "destination", destination)
        if destination is not None:
            if self.channel is DeliveryChannel.EMAIL:
                if not is_email(destination):
                    raise ValueError("email destination is invalid")
            elif not is_e164(destination):
                raise ValueError("phone destination must use E.164")
        if self.enabled:
            if self.channel is DeliveryChannel.EMAIL:
                if destination is None:
                    raise ValueError("email destination is required when enabled")
            else:
                if destination is None:
                    raise ValueError("phone destination is required when enabled")
                if self.consented_at is None:
                    raise ValueError("explicit consent is required when enabled")
        if self.consented_at is not None and self.consented_at.tzinfo is None:
            raise ValueError("consented_at must be timezone-aware")

    @property
    def destination_masked(self) -> str | None:
        return mask_destination(self.channel, self.destination)


@dataclass(frozen=True, slots=True)
class NotificationDelivery:
    id: UUID
    notification_id: UUID
    channel: DeliveryChannel
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempts: int = 0
    last_error_safe: str | None = None
    sent_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.attempts < 0:
            raise ValueError("attempts must be non-negative")
        if self.last_error_safe is not None and len(self.last_error_safe) > 200:
            raise ValueError("last_error_safe is too long")


@dataclass(frozen=True, slots=True)
class NotificationListFilter:
    types: tuple[NotificationType, ...] = ()
    unread_only: bool = False


def mask_destination(channel: DeliveryChannel, destination: str | None) -> str | None:
    if destination is None:
        return None
    if channel is DeliveryChannel.EMAIL:
        local, _, domain = destination.partition("@")
        if not domain:
            return "[REDACTED_EMAIL]"
        return f"{local[:1]}***@{domain}"
    if len(destination) <= 7:
        return "[REDACTED_PHONE]"
    return f"{destination[:3]}{'*' * (len(destination) - 7)}{destination[-4:]}"
