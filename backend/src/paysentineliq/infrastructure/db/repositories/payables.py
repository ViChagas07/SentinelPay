from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paysentineliq.application.ports.payables import (
    PayableTransitionResult,
    ReminderDispatchResult,
)
from paysentineliq.domain.notification import NotificationStatus, NotificationType
from paysentineliq.domain.payables import (
    ACTIVE_STATUSES,
    DEFAULT_CHANNELS,
    DEFAULT_LOCAL_TIME,
    DEFAULT_OFFSETS,
    NotificationChannel,
    Payable,
    PayableStatus,
    ReminderPreference,
)
from paysentineliq.infrastructure.db.models import (
    NotificationModel,
    PayableModel,
    ReminderPreferenceModel,
    UserModel,
)


class SqlAlchemyPayableReadRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_for_owner(
        self,
        payable_id: UUID,
        owner_id: UUID,
    ) -> Payable | None:
        async with self._session_factory() as session:
            model = await session.scalar(
                select(PayableModel).where(
                    PayableModel.id == payable_id,
                    PayableModel.owner_id == owner_id,
                ),
            )
        return _to_payable(model) if model is not None else None

    async def list_for_owner(
        self,
        owner_id: UUID,
        *,
        statuses: tuple[PayableStatus, ...] = (),
        due_from: date | None = None,
        due_to: date | None = None,
        limit: int,
        before: tuple[date, UUID] | None = None,
    ) -> tuple[Payable, ...]:
        statement = select(PayableModel).where(PayableModel.owner_id == owner_id)
        if statuses:
            statement = statement.where(
                PayableModel.status.in_([item.value for item in statuses]),
            )
        if due_from is not None:
            statement = statement.where(PayableModel.due_date >= due_from)
        if due_to is not None:
            statement = statement.where(PayableModel.due_date <= due_to)
        if before is not None:
            due_date, payable_id = before
            statement = statement.where(
                or_(
                    PayableModel.due_date > due_date,
                    and_(
                        PayableModel.due_date == due_date,
                        PayableModel.id > payable_id,
                    ),
                ),
            )
        statement = statement.order_by(
            PayableModel.due_date.asc(),
            PayableModel.id.asc(),
        ).limit(limit)
        async with self._session_factory() as session:
            models = (await session.scalars(statement)).all()
        return tuple(_to_payable(model) for model in models)


class SqlAlchemyPayableWriteRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def confirm(self, payable_id: UUID, owner_id: UUID) -> PayableTransitionResult:
        return await self._transition(
            payable_id,
            owner_id,
            allowed_from=(PayableStatus.PENDING_CONFIRMATION,),
            target=PayableStatus.PENDING,
        )

    async def pay(self, payable_id: UUID, owner_id: UUID) -> PayableTransitionResult:
        return await self._transition(
            payable_id,
            owner_id,
            allowed_from=tuple(ACTIVE_STATUSES),
            target=PayableStatus.PAID,
        )

    async def dismiss(self, payable_id: UUID, owner_id: UUID) -> PayableTransitionResult:
        return await self._transition(
            payable_id,
            owner_id,
            allowed_from=tuple(ACTIVE_STATUSES),
            target=PayableStatus.DISMISSED,
        )

    async def reschedule(
        self,
        payable_id: UUID,
        owner_id: UUID,
        due_date: date,
    ) -> PayableTransitionResult:
        now = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            model = await session.scalar(
                select(PayableModel)
                .where(
                    PayableModel.id == payable_id,
                    PayableModel.owner_id == owner_id,
                )
                .with_for_update(),
            )
            if model is None:
                return PayableTransitionResult(None, "not_found")
            current = PayableStatus(model.status)
            if current not in ACTIVE_STATUSES:
                return PayableTransitionResult(_to_payable(model), "invalid_state")
            if model.due_date == due_date:
                return PayableTransitionResult(_to_payable(model), "unchanged")
            model.due_date = due_date
            model.updated_at = now
            await _cancel_pending_reminders(session, payable_id, now)
            await session.flush()
            return PayableTransitionResult(_to_payable(model), "updated")

    async def _transition(
        self,
        payable_id: UUID,
        owner_id: UUID,
        *,
        allowed_from: tuple[PayableStatus, ...],
        target: PayableStatus,
    ) -> PayableTransitionResult:
        now = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            model = await session.scalar(
                select(PayableModel)
                .where(
                    PayableModel.id == payable_id,
                    PayableModel.owner_id == owner_id,
                )
                .with_for_update(),
            )
            if model is None:
                return PayableTransitionResult(None, "not_found")
            current = PayableStatus(model.status)
            if current is target:
                return PayableTransitionResult(_to_payable(model), "unchanged")
            if current not in allowed_from:
                return PayableTransitionResult(_to_payable(model), "invalid_state")
            model.status = target.value
            model.updated_at = now
            await _cancel_pending_reminders(session, payable_id, now)
            await session.flush()
            return PayableTransitionResult(_to_payable(model), "updated")


class SqlAlchemyReminderPreferenceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_for_user(self, user_id: UUID) -> ReminderPreference:
        async with self._session_factory() as session:
            model = await session.scalar(
                select(ReminderPreferenceModel).where(
                    ReminderPreferenceModel.user_id == user_id,
                ),
            )
        return _to_preference(model, user_id)

    async def upsert(self, preference: ReminderPreference) -> ReminderPreference:
        async with self._session_factory() as session, session.begin():
            model = await session.scalar(
                select(ReminderPreferenceModel).where(
                    ReminderPreferenceModel.user_id == preference.user_id,
                ),
            )
            if model is None:
                model = ReminderPreferenceModel(user_id=preference.user_id)
                session.add(model)
            model.offsets_days = list(preference.sorted_offsets)
            model.local_time = preference.local_time
            model.channels = [channel.value for channel in preference.channels]
            model.updated_at = datetime.now(UTC)
            await session.flush()
            return _to_preference(model, preference.user_id)


class SqlAlchemyPayableReminderRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_due_reminders(
        self,
        now: datetime,
        *,
        lookback_days: int,
    ) -> ReminderDispatchResult:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if lookback_days < 0:
            raise ValueError("lookback_days must be non-negative")
        today = now.astimezone(UTC).date()
        candidates_from = today - timedelta(days=lookback_days + 1)
        candidates_to = today + timedelta(days=32)
        created_ids: list[UUID] = []
        async with self._session_factory() as session, session.begin():
            rows = (
                await session.execute(
                    select(
                        PayableModel,
                        UserModel.timezone,
                        ReminderPreferenceModel,
                    )
                    .join(UserModel, UserModel.id == PayableModel.owner_id)
                    .outerjoin(
                        ReminderPreferenceModel,
                        ReminderPreferenceModel.user_id == PayableModel.owner_id,
                    )
                    .where(
                        PayableModel.status.in_([item.value for item in ACTIVE_STATUSES]),
                        PayableModel.due_date >= candidates_from,
                        PayableModel.due_date <= candidates_to,
                    )
                    .order_by(PayableModel.due_date, PayableModel.id)
                    .limit(500)
                    .with_for_update(skip_locked=True, of=PayableModel),
                )
            ).all()
            for payable, timezone_name, preference_model in rows:
                preference = _to_preference(preference_model, payable.owner_id)
                zone = _zone(timezone_name)
                for offset in preference.sorted_offsets:
                    local_due = datetime.combine(
                        payable.due_date - timedelta(days=offset),
                        preference.local_time,
                        tzinfo=zone,
                    )
                    if local_due.astimezone(UTC) > now:
                        continue
                    notification_type = (
                        NotificationType.PAYABLE_DUE_TODAY
                        if offset == 0
                        else NotificationType.PAYABLE_DUE_SOON
                    )
                    notification_id = uuid4()
                    result = await session.execute(
                        pg_insert(NotificationModel)
                        .values(
                            id=notification_id,
                            owner_id=payable.owner_id,
                            analysis_id=payable.analysis_id,
                            type=notification_type.value,
                            payload={
                                "payable_id": str(payable.id),
                                "due_date": payable.due_date.isoformat(),
                                "offset_days": str(offset),
                                "type": notification_type.value,
                                "channel": NotificationChannel.IN_APP.value,
                            },
                            status=NotificationStatus.PENDING.value,
                            channel=NotificationChannel.IN_APP.value,
                            payable_id=payable.id,
                            reminder_due_date=payable.due_date,
                            reminder_offset_days=offset,
                            created_at=now,
                            updated_at=now,
                        )
                        .on_conflict_do_nothing(
                            index_elements=[
                                "payable_id",
                                "reminder_due_date",
                                "reminder_offset_days",
                                "channel",
                            ],
                        ),
                    )
                    if getattr(result, "rowcount", 0):
                        created_ids.append(notification_id)
        return ReminderDispatchResult(
            created=len(created_ids),
            notification_ids=tuple(created_ids),
        )

    async def mark_overdue(self, now: datetime) -> ReminderDispatchResult:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        created_ids: list[UUID] = []
        async with self._session_factory() as session, session.begin():
            rows = (
                await session.execute(
                    text(
                        """
                        UPDATE payables p
                        SET status = 'overdue', updated_at = :now
                        FROM users u
                        WHERE p.owner_id = u.id
                          AND p.status IN ('pending', 'pending_confirmation')
                          AND p.due_date <
                              (CAST(:now AS timestamptz) AT TIME ZONE u.timezone)::date
                        RETURNING p.id, p.owner_id, p.analysis_id, p.due_date
                        """,
                    ),
                    {"now": now},
                )
            ).all()
            for payable_id, owner_id, analysis_id, due_date in rows:
                notification_id = uuid4()
                result = await session.execute(
                    pg_insert(NotificationModel)
                    .values(
                        id=notification_id,
                        owner_id=owner_id,
                        analysis_id=analysis_id,
                        type=NotificationType.PAYABLE_OVERDUE.value,
                        payload={
                            "payable_id": str(payable_id),
                            "due_date": due_date.isoformat(),
                            "type": NotificationType.PAYABLE_OVERDUE.value,
                            "channel": NotificationChannel.IN_APP.value,
                        },
                        status=NotificationStatus.PENDING.value,
                        channel=NotificationChannel.IN_APP.value,
                        payable_id=payable_id,
                        created_at=now,
                        updated_at=now,
                    )
                    .on_conflict_do_nothing(
                        index_elements=["payable_id"],
                        index_where=text("type = 'payable_overdue'"),
                    ),
                )
                if getattr(result, "rowcount", 0):
                    created_ids.append(notification_id)
        return ReminderDispatchResult(
            created=len(created_ids),
            notification_ids=tuple(created_ids),
        )


async def _cancel_pending_reminders(
    session: AsyncSession,
    payable_id: UUID,
    now: datetime,
) -> None:
    await session.execute(
        update(NotificationModel)
        .where(
            NotificationModel.payable_id == payable_id,
            NotificationModel.type == NotificationType.PAYABLE_DUE_REMINDER.value,
            NotificationModel.status == NotificationStatus.PENDING.value,
        )
        .values(
            status=NotificationStatus.CANCELLED.value,
            updated_at=now,
        ),
    )


def _zone(timezone_name: str | None) -> ZoneInfo:
    if not timezone_name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _to_preference(
    model: ReminderPreferenceModel | None,
    user_id: UUID,
) -> ReminderPreference:
    if model is None:
        return ReminderPreference(user_id=user_id)
    try:
        offsets = tuple(sorted({int(value) for value in model.offsets_days}, reverse=True))
        channels = tuple(NotificationChannel(value) for value in model.channels)
        return ReminderPreference(
            user_id=user_id,
            offsets_days=offsets,
            local_time=model.local_time,
            channels=channels,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    except (TypeError, ValueError):
        return ReminderPreference(
            user_id=user_id,
            offsets_days=DEFAULT_OFFSETS,
            local_time=DEFAULT_LOCAL_TIME,
            channels=DEFAULT_CHANNELS,
        )


def _to_payable(model: PayableModel) -> Payable:
    return Payable(
        id=model.id,
        owner_id=model.owner_id,
        analysis_id=model.analysis_id,
        description=model.description,
        amount_cents=model.amount_cents,
        due_date=model.due_date,
        status=PayableStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
