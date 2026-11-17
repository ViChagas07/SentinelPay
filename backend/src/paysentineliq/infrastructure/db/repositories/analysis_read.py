from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paysentineliq.application.ports.analysis_read_repository import AnalysisSummary
from paysentineliq.domain.analysis import AnalysisDocumentType, AnalysisStatus
from paysentineliq.domain.analysis_progress import stage_from_value
from paysentineliq.domain.scoring import RiskBand
from paysentineliq.infrastructure.db.models import AnalysisModel


class SqlAlchemyAnalysisReadRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_for_owner(
        self,
        analysis_id: UUID,
        owner_id: UUID,
    ) -> AnalysisSummary | None:
        async with self._session_factory() as session:
            model = await session.scalar(
                select(AnalysisModel).where(
                    AnalysisModel.id == analysis_id,
                    AnalysisModel.owner_id == owner_id,
                ),
            )
        return _to_summary(model) if model is not None else None

    async def list_for_owner(
        self,
        owner_id: UUID,
        *,
        limit: int,
        before: tuple[datetime, UUID] | None = None,
    ) -> tuple[AnalysisSummary, ...]:
        statement = select(AnalysisModel).where(AnalysisModel.owner_id == owner_id)
        if before is not None:
            created_at, analysis_id = before
            statement = statement.where(
                or_(
                    AnalysisModel.created_at < created_at,
                    and_(
                        AnalysisModel.created_at == created_at,
                        AnalysisModel.id < analysis_id,
                    ),
                ),
            )
        statement = statement.order_by(
            AnalysisModel.created_at.desc(),
            AnalysisModel.id.desc(),
        ).limit(limit)
        async with self._session_factory() as session:
            models = (await session.scalars(statement)).all()
        return tuple(_to_summary(model) for model in models)


def _to_summary(model: AnalysisModel) -> AnalysisSummary:
    status = (
        AnalysisStatus.RUNNING if model.status == "processing" else AnalysisStatus(model.status)
    )
    return AnalysisSummary(
        id=model.id,
        owner_id=model.owner_id,
        document_id=model.document_id,
        document_type=AnalysisDocumentType(model.document_type),
        status=status,
        score=model.score,
        band=RiskBand(model.band) if model.band is not None else None,
        error_code=model.error_code,
        report_s3_key=model.report_s3_key,
        created_at=model.created_at,
        updated_at=model.updated_at,
        progress_percent=model.progress_percent,
        current_stage=stage_from_value(model.current_stage),
        stage_detail=model.stage_detail,
        stage_started_at=model.stage_started_at,
        cancelled_at=model.cancelled_at,
    )
