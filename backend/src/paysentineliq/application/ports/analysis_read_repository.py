from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from paysentineliq.domain.analysis import AnalysisDocumentType, AnalysisStatus
from paysentineliq.domain.analysis_progress import AnalysisStage
from paysentineliq.domain.scoring import RiskBand


@dataclass(frozen=True, slots=True)
class AnalysisSummary:
    id: UUID
    owner_id: UUID
    document_id: UUID
    document_type: AnalysisDocumentType
    status: AnalysisStatus
    score: int | None
    band: RiskBand | None
    error_code: str | None
    report_s3_key: str | None
    created_at: datetime
    updated_at: datetime
    progress_percent: int = 0
    current_stage: AnalysisStage | None = None
    stage_detail: str | None = None
    stage_started_at: datetime | None = None
    cancelled_at: datetime | None = None


class AnalysisReadRepositoryPort(Protocol):
    async def get_for_owner(
        self,
        analysis_id: UUID,
        owner_id: UUID,
    ) -> AnalysisSummary | None: ...

    async def list_for_owner(
        self,
        owner_id: UUID,
        *,
        limit: int,
        before: tuple[datetime, UUID] | None = None,
    ) -> tuple[AnalysisSummary, ...]: ...
