from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from paysentineliq.domain.notification import (
    DeliveryChannel,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationStatus,
    NotificationType,
)


@dataclass(frozen=True, slots=True)
class DeliveryContext:
    notification: Notification
    email: str
    locale: str
    timezone: str
    preferences: tuple[NotificationPreference, ...]

    def preference_for(self, channel: DeliveryChannel) -> NotificationPreference:
        for preference in self.preferences:
            if preference.channel is channel:
                return preference
        return NotificationPreference(channel=channel)


class NotificationMetricsPort(Protocol):
    def record_notification(
        self,
        channel: str,
        status: str,
        amount: int = 1,
    ) -> None: ...


class NotificationCenterRepositoryPort(Protocol):
    async def list_for_owner(
        self,
        owner_id: UUID,
        *,
        types: tuple[NotificationType, ...] = (),
        unread_only: bool = False,
        limit: int,
        before: tuple[datetime, UUID] | None = None,
    ) -> tuple[Notification, ...]: ...

    async def unread_count(self, owner_id: UUID) -> int: ...

    async def mark_read(
        self,
        notification_id: UUID,
        owner_id: UUID,
        now: datetime,
    ) -> Notification | None: ...

    async def mark_all_read(self, owner_id: UUID, now: datetime) -> int: ...

    async def delete(self, notification_id: UUID, owner_id: UUID) -> bool: ...

    async def set_status(
        self,
        notification_id: UUID,
        status: NotificationStatus,
        now: datetime,
    ) -> None: ...


class NotificationPreferenceRepositoryPort(Protocol):
    async def get_for_user(self, user_id: UUID) -> tuple[NotificationPreference, ...]: ...

    async def upsert(self, preference: NotificationPreference) -> NotificationPreference: ...

    async def update_preferred_locale(self, user_id: UUID, locale: str) -> bool: ...


class NotificationDeliveryRepositoryPort(Protocol):
    async def get_context(self, notification_id: UUID) -> DeliveryContext | None: ...

    async def get_or_create(
        self,
        notification_id: UUID,
        channel: DeliveryChannel,
        now: datetime,
    ) -> NotificationDelivery: ...

    async def mark_sent(self, delivery_id: UUID, now: datetime) -> None: ...

    async def mark_failed(
        self,
        delivery_id: UUID,
        error_safe: str,
        now: datetime,
    ) -> None: ...

    async def mark_skipped(
        self,
        delivery_id: UUID,
        reason_safe: str,
        now: datetime,
    ) -> None: ...

    async def set_notification_status(
        self,
        notification_id: UUID,
        status: NotificationStatus,
        now: datetime,
    ) -> None: ...
