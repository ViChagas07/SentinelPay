from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from paysentineliq.application.errors import (
    InvalidLocaleError,
    InvalidNotificationPreferenceError,
    NotificationNotFoundError,
)
from paysentineliq.application.locale import SUPPORTED_LOCALES
from paysentineliq.application.ports.notifications import (
    NotificationCenterRepositoryPort,
    NotificationPreferenceRepositoryPort,
)
from paysentineliq.domain.notification import (
    DeliveryChannel,
    Notification,
    NotificationPreference,
)
from paysentineliq.domain.user import User


@dataclass(frozen=True, slots=True)
class PreferenceUpdate:
    channel: DeliveryChannel
    enabled: bool = False
    destination: str | None = None
    consent: bool = False


@dataclass(frozen=True, slots=True)
class NotificationPreferencesDTO:
    locale: str
    timezone: str
    channels: tuple[NotificationPreference, ...]


class NotificationCommandHandler:
    def __init__(self, repository: NotificationCenterRepositoryPort) -> None:
        self._repository = repository

    async def mark_read(self, notification_id: UUID, owner_id: UUID) -> Notification:
        notification = await self._repository.mark_read(
            notification_id,
            owner_id,
            datetime.now(UTC),
        )
        if notification is None:
            raise NotificationNotFoundError()
        return notification

    async def mark_all_read(self, owner_id: UUID) -> int:
        return await self._repository.mark_all_read(owner_id, datetime.now(UTC))

    async def delete(self, notification_id: UUID, owner_id: UUID) -> None:
        deleted = await self._repository.delete(notification_id, owner_id)
        if not deleted:
            raise NotificationNotFoundError()


class NotificationPreferenceHandler:
    def __init__(self, repository: NotificationPreferenceRepositoryPort) -> None:
        self._repository = repository

    async def get(self, user: User) -> NotificationPreferencesDTO:
        channels = await self._repository.get_for_user(user.id)
        return NotificationPreferencesDTO(
            locale=user.preferred_locale,
            timezone=user.timezone,
            channels=channels,
        )

    async def update(
        self,
        user: User,
        *,
        locale: str,
        updates: tuple[PreferenceUpdate, ...],
    ) -> NotificationPreferencesDTO:
        if locale not in SUPPORTED_LOCALES:
            raise InvalidLocaleError()
        now = datetime.now(UTC)
        try:
            for update in updates:
                destination = update.destination
                if update.channel is DeliveryChannel.EMAIL:
                    destination = user.email
                await self._repository.upsert(
                    NotificationPreference(
                        channel=update.channel,
                        enabled=update.enabled,
                        destination=destination,
                        consented_at=now if update.consent else None,
                        user_id=user.id,
                    ),
                )
        except ValueError as error:
            raise InvalidNotificationPreferenceError() from error
        if locale != user.preferred_locale:
            updated = await self._repository.update_preferred_locale(user.id, locale)
            if not updated:
                raise InvalidNotificationPreferenceError()
        channels = await self._repository.get_for_user(user.id)
        return NotificationPreferencesDTO(
            locale=locale,
            timezone=user.timezone,
            channels=channels,
        )
