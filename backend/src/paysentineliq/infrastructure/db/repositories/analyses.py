from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisEvent,
    AnalysisEventType,
    AnalysisRecord,
    AnalysisStatus,
    DegradationFlag,
)
from paysentineliq.domain.scoring import RiskBand
from paysentineliq.infrastructure.db.models import AnalysisEventModel, AnalysisModel


class SqlAlchemyAnalysisRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, record: AnalysisRecord) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                AnalysisModel(
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
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                ),
            )

    async def update_state(
        self,
        analysis_id: UUID,
        *,
        status: AnalysisStatus,
        state: Mapping[str, object],
        degradation_flags: tuple[DegradationFlag, ...],
    ) -> None:
        async with self._session_factory() as session, session.begin():
            model = await session.get(AnalysisModel, analysis_id)
            if model is None:
                raise LookupError("analysis not found")
            model.status = status.value
            model.state = dict(state)
            model.degradation_flags = [flag.value for flag in degradation_flags]

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
    ) -> None:
        async with self._session_factory() as session, session.begin():
            model = await session.get(AnalysisModel, analysis_id)
            if model is None:
                raise LookupError("analysis not found")
            model.status = (
                AnalysisStatus.DEGRADED.value
                if degradation_flags
                else AnalysisStatus.COMPLETED.value
            )
            model.score = score
            model.band = band.value
            model.rule_set_version = rule_set_version
            model.model_versions = dict(model_versions)
            model.degradation_flags = [flag.value for flag in degradation_flags]
            model.state = dict(state)
            model.report_s3_key = report_s3_key

    async def fail(
        self,
        analysis_id: UUID,
        *,
        error_code: str,
        state: Mapping[str, object],
    ) -> None:
        async with self._session_factory() as session, session.begin():
            model = await session.get(AnalysisModel, analysis_id)
            if model is None:
                raise LookupError("analysis not found")
            model.status = AnalysisStatus.FAILED.value
            model.error_code = error_code
            model.state = dict(state)

    async def get(self, analysis_id: UUID) -> AnalysisRecord | None:
        async with self._session_factory() as session:
            model = await session.get(AnalysisModel, analysis_id)
        return _to_record(model) if model is not None else None


class SqlAlchemyAnalysisEventRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append(self, event: AnalysisEvent) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                AnalysisEventModel(
                    analysis_id=event.analysis_id,
                    event_type=event.event_type.value,
                    rule_code=event.rule_code,
                    rule_set_version=event.rule_set_version,
                    model_version=event.model_version,
                    degradation_flags=[flag.value for flag in event.degradation_flags],
                    payload=dict(event.payload),
                ),
            )

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
