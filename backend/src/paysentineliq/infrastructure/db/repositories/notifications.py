from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paysentineliq.application.ports.notifications import DeliveryContext
from paysentineliq.domain.notification import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationStatus,
    NotificationType,
)
from paysentineliq.domain.payables import NotificationChannel
from paysentineliq.infrastructure.db.models import (
    NotificationDeliveryModel,
    NotificationModel,
    NotificationPreferenceModel,
    UserModel,
)
from paysentineliq.infrastructure.security.destination_cipher import DestinationCipher


class SqlAlchemyNotificationCenterRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_for_owner(
        self,
        owner_id: UUID,
        *,
        types: tuple[NotificationType, ...] = (),
        unread_only: bool = False,
        limit: int,
        before: tuple[datetime, UUID] | None = None,
    ) -> tuple[Notification, ...]:
        statement = select(NotificationModel).where(NotificationModel.owner_id == owner_id)
        if types:
            statement = statement.where(
                NotificationModel.type.in_([item.value for item in types]),
            )
        if unread_only:
            statement = statement.where(NotificationModel.read_at.is_(None))
        if before is not None:
            created_at, notification_id = before
            statement = statement.where(
                or_(
                    NotificationModel.created_at < created_at,
                    and_(
                        NotificationModel.created_at == created_at,
                        NotificationModel.id < notification_id,
                    ),
                ),
            )
        statement = statement.order_by(
            NotificationModel.created_at.desc(),
            NotificationModel.id.desc(),
        ).limit(limit)
        async with self._session_factory() as session:
            models = (await session.scalars(statement)).all()
        return tuple(_to_notification(model) for model in models)

    async def unread_count(self, owner_id: UUID) -> int:
        async with self._session_factory() as session:
            count = await session.scalar(
                select(func.count(NotificationModel.id)).where(
                    NotificationModel.owner_id == owner_id,
                    NotificationModel.read_at.is_(None),
                ),
            )
        return int(count or 0)

    async def mark_read(
        self,
        notification_id: UUID,
        owner_id: UUID,
        now: datetime,
    ) -> Notification | None:
        async with self._session_factory() as session, session.begin():
            model = await session.scalar(
                select(NotificationModel)
                .where(
                    NotificationModel.id == notification_id,
                    NotificationModel.owner_id == owner_id,
                )
                .with_for_update(),
            )
            if model is None:
                return None
            if model.read_at is None:
                model.read_at = now
                model.updated_at = now
            await session.flush()
            return _to_notification(model)

    async def mark_all_read(self, owner_id: UUID, now: datetime) -> int:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                update(NotificationModel)
                .where(
                    NotificationModel.owner_id == owner_id,
                    NotificationModel.read_at.is_(None),
                )
                .values(read_at=now, updated_at=now),
            )
        return int(getattr(result, "rowcount", 0) or 0)

    async def delete(self, notification_id: UUID, owner_id: UUID) -> bool:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                delete(NotificationModel).where(
                    NotificationModel.id == notification_id,
                    NotificationModel.owner_id == owner_id,
                ),
            )
        return bool(getattr(result, "rowcount", 0) or 0)

    async def set_status(
        self,
        notification_id: UUID,
        status: NotificationStatus,
        now: datetime,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(NotificationModel)
                .where(NotificationModel.id == notification_id)
                .values(status=status.value, updated_at=now),
            )


class SqlAlchemyNotificationPreferenceRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cipher: DestinationCipher,
    ) -> None:
        self._session_factory = session_factory
        self._cipher = cipher

    async def get_for_user(self, user_id: UUID) -> tuple[NotificationPreference, ...]:
        async with self._session_factory() as session:
            user = await session.get(UserModel, user_id)
            if user is None:
                return ()
            return await _load_preferences(session, user, self._cipher)

    async def upsert(self, preference: NotificationPreference) -> NotificationPreference:
        if preference.user_id is None:
            raise ValueError("preference user_id is required")
        now = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            model = await session.scalar(
                select(NotificationPreferenceModel)
                .where(
                    NotificationPreferenceModel.user_id == preference.user_id,
                    NotificationPreferenceModel.channel == preference.channel.value,
                )
                .with_for_update(),
            )
            if model is None:
                model = NotificationPreferenceModel(
                    user_id=preference.user_id,
                    channel=preference.channel.value,
                )
                session.add(model)
            model.enabled = preference.enabled
            if preference.channel is DeliveryChannel.EMAIL:
                model.destination_encrypted = None
                model.consented_at = preference.consented_at or (
                    now if preference.enabled else None
                )
            else:
                model.destination_encrypted = (
                    self._cipher.encrypt(preference.destination)
                    if preference.destination is not None
                    else None
                )
                model.consented_at = preference.consented_at
            model.updated_at = now
            await session.flush()
            user = await session.get(UserModel, preference.user_id)
            if user is None:
                return preference
            loaded = await _load_preferences(session, user, self._cipher)
        for loaded_preference in loaded:
            if loaded_preference.channel is preference.channel:
                return loaded_preference
        return preference

    async def update_preferred_locale(self, user_id: UUID, locale: str) -> bool:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                update(UserModel).where(UserModel.id == user_id).values(preferred_locale=locale),
            )
        return bool(getattr(result, "rowcount", 0) or 0)


class SqlAlchemyNotificationDeliveryRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        cipher: DestinationCipher,
    ) -> None:
        self._session_factory = session_factory
        self._cipher = cipher

    async def get_context(self, notification_id: UUID) -> DeliveryContext | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(NotificationModel, UserModel)
                    .join(UserModel, UserModel.id == NotificationModel.owner_id)
                    .where(NotificationModel.id == notification_id),
                )
            ).first()
            if row is None:
                return None
            notification_model, user = row
            preferences = await _load_preferences(session, user, self._cipher)
        return DeliveryContext(
            notification=_to_notification(notification_model),
            email=user.email,
            locale=user.preferred_locale,
            timezone=user.timezone,
            preferences=preferences,
        )

    async def get_or_create(
        self,
        notification_id: UUID,
        channel: DeliveryChannel,
        now: datetime,
    ) -> NotificationDelivery:
        delivery_id = uuid4()
        async with self._session_factory() as session, session.begin():
            await session.execute(
                pg_insert(NotificationDeliveryModel)
                .values(
                    id=delivery_id,
                    notification_id=notification_id,
                    channel=channel.value,
                    status=DeliveryStatus.PENDING.value,
                    attempts=0,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(
                    index_elements=["notification_id", "channel"],
                ),
            )
            model = await session.scalar(
                select(NotificationDeliveryModel)
                .where(
                    NotificationDeliveryModel.notification_id == notification_id,
                    NotificationDeliveryModel.channel == channel.value,
                )
                .with_for_update(),
            )
            if model is None:
                raise RuntimeError("notification delivery could not be created")
            return _to_delivery(model)

    async def mark_sent(self, delivery_id: UUID, now: datetime) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(NotificationDeliveryModel)
                .where(NotificationDeliveryModel.id == delivery_id)
                .values(
                    status=DeliveryStatus.SENT.value,
                    sent_at=now,
                    last_error_safe=None,
                    updated_at=now,
                ),
            )

    async def mark_failed(
        self,
        delivery_id: UUID,
        error_safe: str,
        now: datetime,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(NotificationDeliveryModel)
                .where(NotificationDeliveryModel.id == delivery_id)
                .values(
                    status=DeliveryStatus.FAILED.value,
                    attempts=NotificationDeliveryModel.attempts + 1,
                    last_error_safe=error_safe,
                    updated_at=now,
                ),
            )

    async def mark_skipped(
        self,
        delivery_id: UUID,
        reason_safe: str,
        now: datetime,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(NotificationDeliveryModel)
                .where(NotificationDeliveryModel.id == delivery_id)
                .values(
                    status=DeliveryStatus.SKIPPED.value,
                    last_error_safe=reason_safe,
                    updated_at=now,
                ),
            )

    async def set_notification_status(
        self,
        notification_id: UUID,
        status: NotificationStatus,
        now: datetime,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(NotificationModel)
                .where(NotificationModel.id == notification_id)
                .values(status=status.value, updated_at=now),
            )


async def _load_preferences(
    session: AsyncSession,
    user: UserModel,
    cipher: DestinationCipher,
) -> tuple[NotificationPreference, ...]:
    models = (
        await session.scalars(
            select(NotificationPreferenceModel).where(
                NotificationPreferenceModel.user_id == user.id,
            ),
        )
    ).all()
    by_channel = {model.channel: model for model in models}
    return (
        _email_preference(user, by_channel.get(DeliveryChannel.EMAIL.value)),
        _phone_preference(
            user.id,
            DeliveryChannel.SMS,
            by_channel.get(DeliveryChannel.SMS.value),
            cipher,
        ),
        _phone_preference(
            user.id,
            DeliveryChannel.WHATSAPP,
            by_channel.get(DeliveryChannel.WHATSAPP.value),
            cipher,
        ),
    )


def _email_preference(
    user: UserModel,
    model: NotificationPreferenceModel | None,
) -> NotificationPreference:
    if model is None:
        return NotificationPreference(
            channel=DeliveryChannel.EMAIL,
            enabled=True,
            destination=user.email,
            consented_at=user.created_at,
            user_id=user.id,
        )
    try:
        return NotificationPreference(
            channel=DeliveryChannel.EMAIL,
            enabled=model.enabled,
            destination=user.email,
            consented_at=model.consented_at or (user.created_at if model.enabled else None),
            user_id=user.id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    except ValueError:
        return NotificationPreference(channel=DeliveryChannel.EMAIL, user_id=user.id)


def _phone_preference(
    user_id: UUID,
    channel: DeliveryChannel,
    model: NotificationPreferenceModel | None,
    cipher: DestinationCipher,
) -> NotificationPreference:
    if model is None:
        return NotificationPreference(channel=channel, user_id=user_id)
    destination: str | None = None
    if model.destination_encrypted:
        try:
            destination = cipher.decrypt(model.destination_encrypted)
        except ValueError:
            destination = None
    try:
        return NotificationPreference(
            channel=channel,
            enabled=model.enabled,
            destination=destination,
            consented_at=model.consented_at,
            user_id=user_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    except ValueError:
        return NotificationPreference(channel=channel, destination=None, user_id=user_id)


def _to_notification(model: NotificationModel) -> Notification:
    return Notification(
        id=model.id,
        owner_id=model.owner_id,
        analysis_id=model.analysis_id,
        type=NotificationType(model.type),
        payload=dict(model.payload),
        status=NotificationStatus(model.status),
        created_at=model.created_at,
        read_at=model.read_at,
        channel=NotificationChannel(model.channel),
        payable_id=model.payable_id,
        reminder_due_date=model.reminder_due_date,
        reminder_offset_days=model.reminder_offset_days,
    )


def _to_delivery(model: NotificationDeliveryModel) -> NotificationDelivery:
    return NotificationDelivery(
        id=model.id,
        notification_id=model.notification_id,
        channel=DeliveryChannel(model.channel),
        status=DeliveryStatus(model.status),
        attempts=model.attempts,
        last_error_safe=model.last_error_safe,
        sent_at=model.sent_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
