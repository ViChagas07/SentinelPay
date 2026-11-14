import os
from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisRecord,
    AnalysisStatus,
)
from paysentineliq.domain.document import Document, DocumentKind
from paysentineliq.domain.notification import (
    NotificationStatus,
    NotificationType,
)
from paysentineliq.domain.payables import (
    NotificationChannel,
    PayableStatus,
    ReminderPreference,
)
from paysentineliq.infrastructure.db.models import (
    AnalysisEventModel,
    AnalysisModel,
    DocumentModel,
    NotificationModel,
    PayableModel,
    ReminderPreferenceModel,
    UserModel,
)
from paysentineliq.infrastructure.db.repositories.analyses import SqlAlchemyAnalysisRepository
from paysentineliq.infrastructure.db.repositories.payables import (
    SqlAlchemyPayableReadRepository,
    SqlAlchemyPayableReminderRepository,
    SqlAlchemyPayableWriteRepository,
    SqlAlchemyReminderPreferenceRepository,
)
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


async def _create_analysis(
    factory: async_sessionmaker[AsyncSession],
    *,
    suffix: str,
    timezone: str = "America/Sao_Paulo",
) -> tuple[UUID, UUID, UUID]:
    async with factory() as session:
        uow = SqlAlchemyUnitOfWork(session)
        async with uow:
            owner = await uow.users.create(
                google_sub=f"payable-{suffix}-{uuid4().hex}",
                email=f"payable-{suffix}-{uuid4().hex}@example.com",
                name="Owner",
            )
            await session.execute(
                update(UserModel).where(UserModel.id == owner.id).values(timezone=timezone),
            )
            document = await uow.documents.add(
                Document(
                    id=uuid4(),
                    owner_id=owner.id,
                    kind=DocumentKind.BANK_SLIP,
                    s3_key=f"users/{owner.id}/bank_slip/{uuid4()}/original.pdf",
                    sha256=uuid4().hex * 2,
                    size=10,
                    content_type="application/pdf",
                    original_name_sanitized="doc.pdf",
                    created_at=_NOW,
                ),
            )
            await uow.commit()
    analysis_id = uuid4()
    await SqlAlchemyAnalysisRepository(factory).create(
        AnalysisRecord(
            id=analysis_id,
            owner_id=owner.id,
            document_id=document.id,
            document_type=AnalysisDocumentType.BOLETO,
            status=AnalysisStatus.QUEUED,
            score=None,
            band=None,
            rule_set_version=None,
            model_versions={},
            degradation_flags=(),
            state={},
            report_s3_key=None,
            error_code=None,
            created_at=_NOW,
            updated_at=_NOW,
        ),
    )
    return owner.id, analysis_id, document.id


async def _add_payable(
    factory: async_sessionmaker[AsyncSession],
    *,
    owner_id: UUID,
    analysis_id: UUID,
    due_date: date,
    status: PayableStatus = PayableStatus.PENDING,
) -> PayableModel:
    async with factory() as session, session.begin():
        model = PayableModel(
            id=uuid4(),
            owner_id=owner_id,
            analysis_id=analysis_id,
            description="Conta de luz",
            amount_cents=18475,
            due_date=due_date,
            status=status.value,
        )
        session.add(model)
    return model


async def _cleanup(
    factory: async_sessionmaker[AsyncSession],
    owners: list[UUID],
    analyses: list[UUID],
    documents: list[UUID],
) -> None:
    async with factory() as session:
        if owners:
            await session.execute(
                delete(NotificationModel).where(NotificationModel.owner_id.in_(owners)),
            )
            await session.execute(
                delete(ReminderPreferenceModel).where(
                    ReminderPreferenceModel.user_id.in_(owners),
                ),
            )
        if analyses:
            await session.execute(
                delete(PayableModel).where(PayableModel.analysis_id.in_(analyses))
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


async def test_list_filters_cursor_and_idor() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owners: list[UUID] = []
    analyses: list[UUID] = []
    documents: list[UUID] = []
    try:
        owner_a, analysis_a, document_a = await _create_analysis(factory, suffix="list-a")
        owner_b, analysis_b, document_b = await _create_analysis(factory, suffix="list-b")
        analysis_a2, document_a2 = await _add_analysis_for_owner(
            factory,
            owner_id=owner_a,
            suffix="list-a2",
        )
        owners = [owner_a, owner_b]
        analyses = [analysis_a, analysis_b, analysis_a2]
        documents = [document_a, document_b, document_a2]
        first = await _add_payable(
            factory,
            owner_id=owner_a,
            analysis_id=analysis_a,
            due_date=date(2026, 1, 10),
        )
        second = await _add_payable(
            factory,
            owner_id=owner_a,
            analysis_id=analysis_a2,
            due_date=date(2026, 1, 12),
            status=PayableStatus.OVERDUE,
        )
        await _add_payable(
            factory,
            owner_id=owner_b,
            analysis_id=analysis_b,
            due_date=date(2026, 1, 11),
        )

        repository = SqlAlchemyPayableReadRepository(factory)
        page = await repository.list_for_owner(owner_a, limit=1)
        next_page = await repository.list_for_owner(
            owner_a,
            limit=10,
            before=(page[-1].due_date, page[-1].id),
        )
        filtered = await repository.list_for_owner(
            owner_a,
            statuses=(PayableStatus.OVERDUE,),
            due_from=date(2026, 1, 11),
            limit=10,
        )
        forbidden = await repository.get_for_owner(first.id, owner_b)

        assert [item.id for item in page] == [first.id]
        assert {item.id for item in next_page} == {second.id}
        assert [item.id for item in filtered] == [second.id]
        assert forbidden is None
    finally:
        await _cleanup(factory, owners, analyses, documents)
        await engine.dispose()


async def test_transitions_are_idempotent_and_cancel_reminders() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owners: list[UUID] = []
    analyses: list[UUID] = []
    documents: list[UUID] = []
    try:
        owner_id, analysis_id, document_id = await _create_analysis(factory, suffix="trans")
        owners = [owner_id]
        analyses = [analysis_id]
        documents = [document_id]
        payable = await _add_payable(
            factory,
            owner_id=owner_id,
            analysis_id=analysis_id,
            due_date=date(2026, 1, 15),
            status=PayableStatus.PENDING_CONFIRMATION,
        )
        async with factory() as session, session.begin():
            session.add(
                NotificationModel(
                    owner_id=owner_id,
                    analysis_id=analysis_id,
                    type=NotificationType.PAYABLE_DUE_REMINDER.value,
                    payload={"payable_id": str(payable.id)},
                    status=NotificationStatus.PENDING.value,
                    channel=NotificationChannel.IN_APP.value,
                    payable_id=payable.id,
                    reminder_due_date=date(2026, 1, 15),
                    reminder_offset_days=3,
                ),
            )

        write = SqlAlchemyPayableWriteRepository(factory)
        confirmed = await write.confirm(payable.id, owner_id)
        repeated = await write.confirm(payable.id, owner_id)
        rescheduled = await write.reschedule(payable.id, owner_id, date(2026, 1, 20))
        paid = await write.pay(payable.id, owner_id)
        paid_again = await write.pay(payable.id, owner_id)
        invalid = await write.dismiss(payable.id, owner_id)
        missing = await write.pay(uuid4(), owner_id)

        async with factory() as session:
            notification = await session.scalar(
                select(NotificationModel).where(NotificationModel.payable_id == payable.id),
            )

        assert confirmed.outcome == "updated"
        assert confirmed.payable is not None
        assert confirmed.payable.status is PayableStatus.PENDING
        assert repeated.outcome == "unchanged"
        assert rescheduled.outcome == "updated"
        assert rescheduled.payable is not None
        assert rescheduled.payable.due_date == date(2026, 1, 20)
        assert paid.payable is not None
        assert paid.payable.status is PayableStatus.PAID
        assert paid_again.outcome == "unchanged"
        assert invalid.outcome == "invalid_state"
        assert missing.outcome == "not_found"
        assert notification is not None
        assert notification.status == NotificationStatus.CANCELLED.value
    finally:
        await _cleanup(factory, owners, analyses, documents)
        await engine.dispose()


async def test_preferences_upsert_and_defaults() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owners: list[UUID] = []
    analyses: list[UUID] = []
    documents: list[UUID] = []
    try:
        owner_id, analysis_id, document_id = await _create_analysis(factory, suffix="pref")
        owners = [owner_id]
        analyses = [analysis_id]
        documents = [document_id]
        repository = SqlAlchemyReminderPreferenceRepository(factory)

        default = await repository.get_for_user(owner_id)
        saved = await repository.upsert(
            ReminderPreference(
                user_id=owner_id,
                offsets_days=(7, 0),
                local_time=time(18, 30),
                channels=(NotificationChannel.IN_APP,),
            ),
        )
        loaded = await repository.get_for_user(owner_id)

        assert default.offsets_days == (3, 1, 0)
        assert saved.offsets_days == (7, 0)
        assert loaded.local_time == time(18, 30)
    finally:
        await _cleanup(factory, owners, analyses, documents)
        await engine.dispose()


async def test_reminders_respect_timezone_rollover_and_do_not_duplicate() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owners: list[UUID] = []
    analyses: list[UUID] = []
    documents: list[UUID] = []
    try:
        sao_paulo, analysis_sp, doc_sp = await _create_analysis(
            factory,
            suffix="tz-sp",
            timezone="America/Sao_Paulo",
        )
        kiritimati, analysis_ki, doc_ki = await _create_analysis(
            factory,
            suffix="tz-ki",
            timezone="Pacific/Kiritimati",
        )
        owners = [sao_paulo, kiritimati]
        analyses = [analysis_sp, analysis_ki]
        documents = [doc_sp, doc_ki]
        await _add_payable(
            factory,
            owner_id=sao_paulo,
            analysis_id=analysis_sp,
            due_date=date(2026, 1, 15),
        )
        await _add_payable(
            factory,
            owner_id=kiritimati,
            analysis_id=analysis_ki,
            due_date=date(2026, 1, 15),
        )
        repository = SqlAlchemyPayableReminderRepository(factory)

        before = await repository.create_due_reminders(
            datetime(2026, 1, 11, 18, 59, tzinfo=UTC),
            lookback_days=7,
        )
        after = await repository.create_due_reminders(
            datetime(2026, 1, 11, 19, 0, tzinfo=UTC),
            lookback_days=7,
        )
        repeated = await repository.create_due_reminders(
            datetime(2026, 1, 11, 19, 0, tzinfo=UTC),
            lookback_days=7,
        )
        sao_before = await repository.create_due_reminders(
            datetime(2026, 1, 12, 11, 59, tzinfo=UTC),
            lookback_days=7,
        )
        sao_after = await repository.create_due_reminders(
            datetime(2026, 1, 12, 12, 0, tzinfo=UTC),
            lookback_days=7,
        )

        async with factory() as session:
            reminders = (
                await session.scalars(
                    select(NotificationModel).where(
                        NotificationModel.payable_id.is_not(None),
                    ),
                )
            ).all()
            kiritimati_count = sum(1 for item in reminders if item.owner_id == kiritimati)

        assert before == 0
        assert after == 1
        assert repeated == 0
        assert kiritimati_count == 1
        assert sao_before == 0
        assert sao_after == 1
    finally:
        await _cleanup(factory, owners, analyses, documents)
        await engine.dispose()


async def test_mark_overdue_uses_user_local_date() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owners: list[UUID] = []
    analyses: list[UUID] = []
    documents: list[UUID] = []
    try:
        owner_id, analysis_id, document_id = await _create_analysis(
            factory,
            suffix="overdue",
            timezone="America/Sao_Paulo",
        )
        owners = [owner_id]
        analyses = [analysis_id]
        documents = [document_id]
        payable = await _add_payable(
            factory,
            owner_id=owner_id,
            analysis_id=analysis_id,
            due_date=date(2026, 1, 10),
        )
        repository = SqlAlchemyPayableReminderRepository(factory)

        updated = await repository.mark_overdue(
            datetime(2026, 1, 11, 12, 0, tzinfo=UTC),
        )
        repeated = await repository.mark_overdue(
            datetime(2026, 1, 11, 12, 0, tzinfo=UTC),
        )
        async with factory() as session:
            status = await session.scalar(
                select(PayableModel.status).where(PayableModel.id == payable.id),
            )
            pending = await session.scalar(
                select(func.count(NotificationModel.id)).where(
                    NotificationModel.payable_id == payable.id,
                ),
            )

        assert updated == 1
        assert repeated == 0
        assert status == PayableStatus.OVERDUE.value
        assert pending == 0
    finally:
        await _cleanup(factory, owners, analyses, documents)
        await engine.dispose()


async def _add_analysis_for_owner(
    factory: async_sessionmaker[AsyncSession],
    *,
    owner_id: UUID,
    suffix: str,
) -> tuple[UUID, UUID]:
    async with factory() as session:
        uow = SqlAlchemyUnitOfWork(session)
        async with uow:
            document = await uow.documents.add(
                Document(
                    id=uuid4(),
                    owner_id=owner_id,
                    kind=DocumentKind.BANK_SLIP,
                    s3_key=f"users/{owner_id}/bank_slip/{uuid4()}/original.pdf",
                    sha256=uuid4().hex * 2,
                    size=10,
                    content_type="application/pdf",
                    original_name_sanitized=f"{suffix}.pdf",
                    created_at=_NOW,
                ),
            )
            await uow.commit()
    analysis_id = uuid4()
    await SqlAlchemyAnalysisRepository(factory).create(
        AnalysisRecord(
            id=analysis_id,
            owner_id=owner_id,
            document_id=document.id,
            document_type=AnalysisDocumentType.BOLETO,
            status=AnalysisStatus.QUEUED,
            score=None,
            band=None,
            rule_set_version=None,
            model_versions={},
            degradation_flags=(),
            state={},
            report_s3_key=None,
            error_code=None,
            created_at=_NOW,
            updated_at=_NOW,
        ),
    )
    return analysis_id, document.id
