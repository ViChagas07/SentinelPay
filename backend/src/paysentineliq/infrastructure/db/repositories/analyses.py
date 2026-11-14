from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisEvent,
    AnalysisEventType,
    AnalysisRecord,
    AnalysisStatus,
    DegradationFlag,
)
from paysentineliq.domain.notification import Notification, NotificationStatus, NotificationType
from paysentineliq.domain.scoring import RiskBand
from paysentineliq.infrastructure.db.models import (
    AnalysisEventModel,
    AnalysisModel,
    NotificationModel,
)

_TERMINAL = (
    AnalysisStatus.COMPLETED.value,
    AnalysisStatus.DEGRADED.value,
    AnalysisStatus.FAILED.value,
)
_ACTIVE = (
    AnalysisStatus.QUEUED.value,
    AnalysisStatus.PROCESSING.value,
)


def _event_model(event: AnalysisEvent) -> AnalysisEventModel:
    return AnalysisEventModel(
        analysis_id=event.analysis_id,
        event_type=event.event_type.value,
        rule_code=event.rule_code,
        rule_set_version=event.rule_set_version,
        model_version=event.model_version,
        degradation_flags=[flag.value for flag in event.degradation_flags],
        payload=dict(event.payload),
    )


def _notification_model(notification: Notification) -> NotificationModel:
    return NotificationModel(
        id=notification.id,
        owner_id=notification.owner_id,
        analysis_id=notification.analysis_id,
        type=notification.type.value,
        payload=dict(notification.payload),
        status=notification.status.value,
    )


def _analysis_model(record: AnalysisRecord) -> AnalysisModel:
    return AnalysisModel(
        id=record.id,
        owner_id=record.owner_id,
        document_id=record.document_id,
        document_type=record.document_type.value,
        status=record.status.value,
        score=record.score,
        band=record.band.value if record.band is not None else None,
        rule_set_version=record.rule_set_version,
        model_versions=dict(record.model_versions),
        degradation_flags=[flag.value for flag in record.degradation_flags],
        state=dict(record.state),
        report_s3_key=record.report_s3_key,
        error_code=record.error_code,
        idempotency_key=record.idempotency_key,
        idempotency_request_hash=record.idempotency_request_hash,
        task_id=record.task_id,
        processing_started_at=record.processing_started_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class SqlAlchemyAnalysisRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create(
        self,
        record: AnalysisRecord,
        *,
        event: AnalysisEvent | None = None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(_analysis_model(record))
            if event is not None:
                session.add(_event_model(event))

    async def update_state(
        self,
        analysis_id: UUID,
        *,
        status: AnalysisStatus,
        state: Mapping[str, object],
        degradation_flags: tuple[DegradationFlag, ...],
        event: AnalysisEvent | None = None,
    ) -> bool:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                update(AnalysisModel)
                .where(
                    AnalysisModel.id == analysis_id,
                    AnalysisModel.status.notin_(_TERMINAL),
                )
                .values(
                    status=status.value,
                    state=dict(state),
                    degradation_flags=[flag.value for flag in degradation_flags],
                    updated_at=func.now(),
                )
                .returning(AnalysisModel.id),
            )
            if result.scalar_one_or_none() is None:
                return False
            if event is not None:
                session.add(_event_model(event))
            return True

    async def complete(
        self,
        analysis_id: UUID,
        *,
        score: int,
        band: RiskBand,
        rule_set_version: str,
        model_versions: Mapping[str, str],
        degradation_flags: tuple[DegradationFlag, ...],
        state: Mapping[str, object],
        report_s3_key: str,
        event: AnalysisEvent | None = None,
        notifications: tuple[Notification, ...] = (),
    ) -> bool:
        target = (
            AnalysisStatus.DEGRADED.value if degradation_flags else AnalysisStatus.COMPLETED.value
        )
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                update(AnalysisModel)
                .where(
                    AnalysisModel.id == analysis_id,
                    AnalysisModel.status.notin_(_TERMINAL),
                )
                .values(
                    status=target,
                    score=score,
                    band=band.value,
                    rule_set_version=rule_set_version,
                    model_versions=dict(model_versions),
                    degradation_flags=[flag.value for flag in degradation_flags],
                    state=dict(state),
                    report_s3_key=report_s3_key,
                    error_code=None,
                    updated_at=func.now(),
                )
                .returning(AnalysisModel.id),
            )
            if result.scalar_one_or_none() is None:
                return False
            if event is not None:
                session.add(_event_model(event))
            for notification in notifications:
                session.add(_notification_model(notification))
            return True

    async def fail(
        self,
        analysis_id: UUID,
        *,
        error_code: str,
        state: Mapping[str, object],
        event: AnalysisEvent | None = None,
        notifications: tuple[Notification, ...] = (),
    ) -> bool:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                update(AnalysisModel)
                .where(
                    AnalysisModel.id == analysis_id,
                    AnalysisModel.status.notin_(_TERMINAL),
                )
                .values(
                    status=AnalysisStatus.FAILED.value,
                    error_code=error_code,
                    state=dict(state),
                    updated_at=func.now(),
                )
                .returning(AnalysisModel.id),
            )
            if result.scalar_one_or_none() is None:
                return False
            if event is not None:
                session.add(_event_model(event))
            for notification in notifications:
                session.add(_notification_model(notification))
            return True

    async def requeue_for_retry(
        self,
        analysis_id: UUID,
        *,
        error_code: str,
        state: Mapping[str, object],
        event: AnalysisEvent,
    ) -> bool:
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                update(AnalysisModel)
                .where(
                    AnalysisModel.id == analysis_id,
                    AnalysisModel.status == AnalysisStatus.PROCESSING.value,
                )
                .values(
                    status=AnalysisStatus.QUEUED.value,
                    error_code=error_code,
                    processing_started_at=None,
                    state=dict(state),
                    updated_at=func.now(),
                )
                .returning(AnalysisModel.id),
            )
            if result.scalar_one_or_none() is None:
                return False
            session.add(_event_model(event))
            return True

    async def claim_for_processing(
        self,
        analysis_id: UUID,
        *,
        task_id: str,
        lease_seconds: int,
        event: AnalysisEvent | None = None,
    ) -> AnalysisRecord | None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        now = self._clock()
        cutoff = now - timedelta(seconds=lease_seconds)
        async with self._session_factory() as session, session.begin():
            result = await session.execute(
                update(AnalysisModel)
                .where(
                    AnalysisModel.id == analysis_id,
                    or_(
                        AnalysisModel.status == AnalysisStatus.QUEUED.value,
                        and_(
                            AnalysisModel.status == AnalysisStatus.PROCESSING.value,
                            or_(
                                AnalysisModel.processing_started_at.is_(None),
                                AnalysisModel.processing_started_at < cutoff,
                            ),
                        ),
                    ),
                )
                .values(
                    status=AnalysisStatus.PROCESSING.value,
                    task_id=task_id,
                    processing_started_at=now,
                    updated_at=func.now(),
                )
                .returning(AnalysisModel),
            )
            model = result.scalar_one_or_none()
            if model is None:
                return None
            if event is not None:
                session.add(_event_model(event))
            return _to_record(model)

    async def get(self, analysis_id: UUID) -> AnalysisRecord | None:
        async with self._session_factory() as session:
            model = await session.get(AnalysisModel, analysis_id)
        return _to_record(model) if model is not None else None

    async def find_by_idempotency(
        self,
        owner_id: UUID,
        idempotency_key: str,
    ) -> AnalysisRecord | None:
        async with self._session_factory() as session:
            model = await session.scalar(
                select(AnalysisModel).where(
                    AnalysisModel.owner_id == owner_id,
                    AnalysisModel.idempotency_key == idempotency_key,
                ),
            )
        return _to_record(model) if model is not None else None

    async def count_active_for_owner(self, owner_id: UUID) -> int:
        async with self._session_factory() as session:
            value = await session.scalar(
                select(func.count(AnalysisModel.id)).where(
                    AnalysisModel.owner_id == owner_id,
                    AnalysisModel.status.in_(_ACTIVE),
                ),
            )
        return int(value or 0)

    async def list_stale_processing(self, before: datetime) -> tuple[AnalysisRecord, ...]:
        async with self._session_factory() as session:
            models = (
                await session.scalars(
                    select(AnalysisModel).where(
                        AnalysisModel.status == AnalysisStatus.PROCESSING.value,
                        or_(
                            AnalysisModel.processing_started_at.is_(None),
                            AnalysisModel.processing_started_at < before,
                        ),
                    ),
                )
            ).all()
        return tuple(_to_record(model) for model in models)


class SqlAlchemyAnalysisCreationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _lock(self, key: str) -> None:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": key},
        )

    async def lock_idempotency(self, owner_id: UUID, idempotency_key: str) -> None:
        await self._lock(f"analysis-idempotency:{owner_id}:{idempotency_key}")

    async def lock_quota(self, owner_id: UUID) -> None:
        await self._lock(f"analysis-quota:{owner_id}")

    async def find_by_idempotency(
        self,
        owner_id: UUID,
        idempotency_key: str,
    ) -> AnalysisRecord | None:
        model = await self._session.scalar(
            select(AnalysisModel).where(
                AnalysisModel.owner_id == owner_id,
                AnalysisModel.idempotency_key == idempotency_key,
            ),
        )
        return _to_record(model) if model is not None else None

    async def count_active_for_owner(self, owner_id: UUID) -> int:
        value = await self._session.scalar(
            select(func.count(AnalysisModel.id)).where(
                AnalysisModel.owner_id == owner_id,
                AnalysisModel.status.in_(_ACTIVE),
            ),
        )
        return int(value or 0)

    async def add(
        self,
        record: AnalysisRecord,
        *,
        event: AnalysisEvent | None = None,
    ) -> None:
        self._session.add(_analysis_model(record))
        if event is not None:
            self._session.add(_event_model(event))


class SqlAlchemyNotificationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_pending_for_analysis(
        self,
        analysis_id: UUID,
    ) -> tuple[Notification, ...]:
        async with self._session_factory() as session:
            models = (
                await session.scalars(
                    select(NotificationModel)
                    .where(
                        NotificationModel.analysis_id == analysis_id,
                        NotificationModel.status == NotificationStatus.PENDING.value,
                    )
                    .order_by(NotificationModel.created_at, NotificationModel.id),
                )
            ).all()
        return tuple(_to_notification(model) for model in models)

    async def mark_dispatched(self, notification_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(NotificationModel)
                .where(NotificationModel.id == notification_id)
                .values(status=NotificationStatus.DISPATCHED.value, updated_at=func.now()),
            )


def _to_record(model: AnalysisModel) -> AnalysisRecord:
    return AnalysisRecord(
        id=model.id,
        owner_id=model.owner_id,
        document_id=model.document_id,
        document_type=AnalysisDocumentType(model.document_type),
        status=AnalysisStatus(model.status),
        score=model.score,
        band=RiskBand(model.band) if model.band is not None else None,
        rule_set_version=model.rule_set_version,
        model_versions=dict(model.model_versions or {}),
        degradation_flags=tuple(DegradationFlag(flag) for flag in (model.degradation_flags or [])),
        state=dict(model.state or {}),
        report_s3_key=model.report_s3_key,
        error_code=model.error_code,
        created_at=model.created_at,
        updated_at=model.updated_at,
        idempotency_key=model.idempotency_key,
        idempotency_request_hash=model.idempotency_request_hash,
        task_id=model.task_id,
        processing_started_at=model.processing_started_at,
    )


def _to_notification(model: NotificationModel) -> Notification:
    return Notification(
        id=model.id,
        owner_id=model.owner_id,
        analysis_id=model.analysis_id,
        type=NotificationType(model.type),
        payload=dict(model.payload or {}),
        status=NotificationStatus(model.status),
        created_at=model.created_at,
    )


def _to_event(model: AnalysisEventModel) -> AnalysisEvent:
    return AnalysisEvent(
        analysis_id=model.analysis_id,
        event_type=AnalysisEventType(model.event_type),
        rule_code=model.rule_code,
        rule_set_version=model.rule_set_version,
        model_version=model.model_version,
        degradation_flags=tuple(DegradationFlag(flag) for flag in (model.degradation_flags or [])),
        payload=dict(model.payload or {}),
        created_at=model.created_at,
    )


class SqlAlchemyAnalysisEventRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append(self, event: AnalysisEvent) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(_event_model(event))

    async def list_for_analysis(
        self,
        analysis_id: UUID,
    ) -> tuple[AnalysisEvent, ...]:
        async with self._session_factory() as session:
            models = (
                await session.scalars(
                    select(AnalysisEventModel)
                    .where(AnalysisEventModel.analysis_id == analysis_id)
                    .order_by(AnalysisEventModel.created_at, AnalysisEventModel.id),
                )
            ).all()
        return tuple(_to_event(model) for model in models)
