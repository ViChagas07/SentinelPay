import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from paysentineliq.domain.notification import (
    DeliveryChannel,
    DeliveryStatus,
    NotificationPreference,
    NotificationStatus,
    NotificationType,
)
from paysentineliq.infrastructure.db.models import (
    AnalysisEventModel,
    AnalysisModel,
    DocumentModel,
    NotificationDeliveryModel,
    NotificationModel,
    NotificationPreferenceModel,
    PayableModel,
    ReminderPreferenceModel,
    UserModel,
)
from paysentineliq.infrastructure.db.repositories.notifications import (
    SqlAlchemyNotificationCenterRepository,
    SqlAlchemyNotificationDeliveryRepository,
    SqlAlchemyNotificationPreferenceRepository,
)
from paysentineliq.infrastructure.security.destination_cipher import DestinationCipher
from tests.integration.test_payables_repository import _create_analysis

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_SECRET = "notification-test-secret"


async def _add_notification(
    factory: async_sessionmaker[AsyncSession],
    *,
    owner_id: UUID,
    analysis_id: UUID,
    notification_type: NotificationType = NotificationType.ANALYSIS_COMPLETED,
    created_at: datetime = _NOW,
    read_at: datetime | None = None,
    payload: dict[str, str] | None = None,
) -> UUID:
    notification_id = uuid4()
    async with factory() as session, session.begin():
        session.add(
            NotificationModel(
                id=notification_id,
                owner_id=owner_id,
                analysis_id=analysis_id,
                type=notification_type.value,
                payload=payload or {"analysis_id": str(analysis_id)},
                status=NotificationStatus.PENDING.value,
                channel="in_app",
                created_at=created_at,
                updated_at=created_at,
                read_at=read_at,
            ),
        )
    return notification_id


async def _cleanup(
    factory: async_sessionmaker[AsyncSession],
    owners: list[UUID],
    analyses: list[UUID],
    documents: list[UUID],
) -> None:
    async with factory() as session:
        if owners:
            await session.execute(
                delete(NotificationDeliveryModel).where(
                    NotificationDeliveryModel.notification_id.in_(
                        select(NotificationModel.id).where(
                            NotificationModel.owner_id.in_(owners),
                        ),
                    ),
                ),
            )
            await session.execute(
                delete(NotificationModel).where(NotificationModel.owner_id.in_(owners)),
            )
            await session.execute(
                delete(NotificationPreferenceModel).where(
                    NotificationPreferenceModel.user_id.in_(owners),
                ),
            )
            await session.execute(
                delete(ReminderPreferenceModel).where(
                    ReminderPreferenceModel.user_id.in_(owners),
                ),
            )
        if analyses:
            await session.execute(
                delete(PayableModel).where(PayableModel.analysis_id.in_(analyses)),
            )
            await session.execute(
                delete(AnalysisEventModel).where(AnalysisEventModel.analysis_id.in_(analyses)),
            )
            await session.execute(delete(AnalysisModel).where(AnalysisModel.id.in_(analyses)))
        if documents:
            await session.execute(delete(DocumentModel).where(DocumentModel.id.in_(documents)))
        if owners:
            await session.execute(delete(UserModel).where(UserModel.id.in_(owners)))
        await session.commit()


async def test_center_list_filters_cursor_read_and_idor() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owners: list[UUID] = []
    analyses: list[UUID] = []
    documents: list[UUID] = []
    try:
        owner_a, analysis_a, document_a = await _create_analysis(factory, suffix="ntf-a")
        owner_b, analysis_b, document_b = await _create_analysis(factory, suffix="ntf-b")
        owners = [owner_a, owner_b]
        analyses = [analysis_a, analysis_b]
        documents = [document_a, document_b]
        first = await _add_notification(
            factory,
            owner_id=owner_a,
            analysis_id=analysis_a,
            notification_type=NotificationType.PAYABLE_DUE_SOON,
            created_at=_NOW - timedelta(hours=2),
            read_at=_NOW,
        )
        second = await _add_notification(
            factory,
            owner_id=owner_a,
            analysis_id=analysis_a,
            notification_type=NotificationType.HIGH_RISK_DETECTED,
            created_at=_NOW - timedelta(hours=1),
        )
        third = await _add_notification(
            factory,
            owner_id=owner_a,
            analysis_id=analysis_a,
            notification_type=NotificationType.PAYABLE_DUE_SOON,
            created_at=_NOW,
        )
        foreign = await _add_notification(
            factory,
            owner_id=owner_b,
            analysis_id=analysis_b,
            created_at=_NOW - timedelta(hours=3),
        )
        repository = SqlAlchemyNotificationCenterRepository(factory)

        newest = await repository.list_for_owner(owner_a, limit=2)
        assert newest[-1].created_at is not None
        older = await repository.list_for_owner(
            owner_a,
            limit=2,
            before=(newest[-1].created_at, newest[-1].id),
        )
        due_soon = await repository.list_for_owner(
            owner_a,
            types=(NotificationType.PAYABLE_DUE_SOON,),
            limit=10,
        )
        unread = await repository.list_for_owner(owner_a, unread_only=True, limit=10)
        foreign_page = await repository.list_for_owner(owner_b, limit=10)
        unread_before = await repository.unread_count(owner_a)

        marked = await repository.mark_read(third, owner_a, _NOW + timedelta(minutes=1))
        forbidden_read = await repository.mark_read(third, owner_b, _NOW)
        marked_all = await repository.mark_all_read(owner_a, _NOW + timedelta(minutes=2))
        unread_after = await repository.unread_count(owner_a)
        forbidden_delete = await repository.delete(foreign, owner_a)
        deleted = await repository.delete(third, owner_a)

        async with factory() as session:
            foreign_still_there = await session.get(NotificationModel, foreign)
            remaining = (
                await session.scalars(
                    select(NotificationModel.id).where(NotificationModel.owner_id == owner_a),
                )
            ).all()

        assert [item.id for item in newest] == [third, second]
        assert [item.id for item in older] == [first]
        assert {item.id for item in due_soon} == {first, third}
        assert {item.id for item in unread} == {second, third}
        assert [item.id for item in foreign_page] == [foreign]
        assert unread_before == 2
        assert marked is not None and marked.id == third and marked.is_read
        assert forbidden_read is None
        assert marked_all == 1
        assert unread_after == 0
        assert forbidden_delete is False
        assert deleted is True
        assert foreign_still_there is not None
        assert set(remaining) == {first, second}
    finally:
        await _cleanup(factory, owners, analyses, documents)
        await engine.dispose()


async def test_preferences_defaults_opt_in_and_encrypted_phone() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owners: list[UUID] = []
    analyses: list[UUID] = []
    documents: list[UUID] = []
    try:
        owner_id, analysis_id, document_id = await _create_analysis(factory, suffix="ntf-pref")
        owners = [owner_id]
        analyses = [analysis_id]
        documents = [document_id]
        repository = SqlAlchemyNotificationPreferenceRepository(
            factory,
            DestinationCipher(_SECRET),
        )

        defaults = {item.channel: item for item in await repository.get_for_user(owner_id)}
        async with factory() as session:
            user = await session.get(UserModel, owner_id)
            assert user is not None
            account_email = user.email
        assert defaults[DeliveryChannel.EMAIL].enabled is True
        assert defaults[DeliveryChannel.EMAIL].destination == account_email
        assert defaults[DeliveryChannel.SMS].enabled is False
        assert defaults[DeliveryChannel.WHATSAPP].enabled is False

        updated = await repository.upsert(
            NotificationPreference(
                channel=DeliveryChannel.SMS,
                enabled=True,
                destination="+5511999999999",
                consented_at=_NOW,
                user_id=owner_id,
            ),
        )
        assert updated.enabled is True
        assert updated.destination == "+5511999999999"
        assert updated.destination_masked == "+55*******9999"

        async with factory() as session:
            stored = await session.scalar(
                select(NotificationPreferenceModel).where(
                    NotificationPreferenceModel.user_id == owner_id,
                    NotificationPreferenceModel.channel == "sms",
                ),
            )
            assert stored is not None
            assert stored.destination_encrypted is not None
            assert stored.destination_encrypted.startswith("v1:")
            assert "+5511999999999" not in stored.destination_encrypted

        changed = await repository.update_preferred_locale(owner_id, "ja")
        async with factory() as session:
            user = await session.get(UserModel, owner_id)
        assert changed is True
        assert user is not None and user.preferred_locale == "ja"
    finally:
        await _cleanup(factory, owners, analyses, documents)
        await engine.dispose()


async def test_delivery_is_idempotent_and_records_safe_error() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owners: list[UUID] = []
    analyses: list[UUID] = []
    documents: list[UUID] = []
    try:
        owner_id, analysis_id, document_id = await _create_analysis(factory, suffix="ntf-del")
        owners = [owner_id]
        analyses = [analysis_id]
        documents = [document_id]
        notification_id = await _add_notification(
            factory,
            owner_id=owner_id,
            analysis_id=analysis_id,
            notification_type=NotificationType.PAYABLE_DUE_SOON,
            payload={
                "payable_id": str(uuid4()),
                "due_date": "2026-01-15",
                "offset_days": "3",
                "type": "payable_due_soon",
                "channel": "in_app",
            },
        )
        repository = SqlAlchemyNotificationDeliveryRepository(
            factory,
            DestinationCipher(_SECRET),
        )

        context = await repository.get_context(notification_id)
        first = await repository.get_or_create(notification_id, DeliveryChannel.EMAIL, _NOW)
        second = await repository.get_or_create(notification_id, DeliveryChannel.EMAIL, _NOW)
        await repository.mark_failed(first.id, "smtp_error", _NOW)
        failed = await repository.get_or_create(notification_id, DeliveryChannel.EMAIL, _NOW)
        await repository.mark_sent(first.id, _NOW)
        await repository.set_notification_status(
            notification_id,
            NotificationStatus.DISPATCHED,
            _NOW,
        )
        async with factory() as session:
            stored_notification = await session.get(NotificationModel, notification_id)

        assert context is not None
        assert context.notification.id == notification_id
        assert context.locale == "pt-BR"
        assert context.email.endswith("@example.com")
        assert first.id == second.id
        assert failed.status is DeliveryStatus.FAILED
        assert failed.attempts == 1
        assert failed.last_error_safe == "smtp_error"
        assert stored_notification is not None
        assert stored_notification.status == NotificationStatus.DISPATCHED.value
    finally:
        await _cleanup(factory, owners, analyses, documents)
        await engine.dispose()
