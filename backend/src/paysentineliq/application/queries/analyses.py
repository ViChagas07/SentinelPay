import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from paysentineliq.application.errors import AnalysisNotFoundError
from paysentineliq.application.ports.analysis_read_repository import (
    AnalysisReadRepositoryPort,
    AnalysisSummary,
)
from paysentineliq.application.ports.storage import StoragePort
from paysentineliq.application.queries.analysis_cursor import decode_cursor, encode_cursor
from paysentineliq.domain.analysis import AnalysisStatus
from paysentineliq.domain.analysis_progress import AnalysisStage
from paysentineliq.domain.scoring import RiskBand

_logger = logging.getLogger("paysentineliq")
_MAX_REPORT_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class AnalysisEvidenceDTO:
    rule_id: str
    severity: str
    weight: int
    message_key: str
    source: str


@dataclass(frozen=True, slots=True)
class AnalysisResultDTO:
    score: int
    band: RiskBand
    base_score: int
    llm_adjustment: int
    evidence: tuple[AnalysisEvidenceDTO, ...]
    justification: str
    inconsistencies: tuple[str, ...]
    degradation_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnalysisProgressDTO:
    percent: int
    stage: AnalysisStage | None
    detail: str | None
    started_at: datetime | None
    indeterminate: bool


@dataclass(frozen=True, slots=True)
class AnalysisDetailDTO:
    id: UUID
    status: AnalysisStatus
    kind: str
    created_at: datetime
    updated_at: datetime
    error_code: str | None
    result_available: bool
    result: AnalysisResultDTO | None
    progress: AnalysisProgressDTO = field(
        default_factory=lambda: AnalysisProgressDTO(
            percent=0,
            stage=None,
            detail=None,
            started_at=None,
            indeterminate=False,
        ),
    )
    cancelled_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AnalysisListItemDTO:
    id: UUID
    status: AnalysisStatus
    kind: str
    score: int | None
    band: RiskBand | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AnalysisListDTO:
    items: tuple[AnalysisListItemDTO, ...]
    next_cursor: str | None


class GetAnalysisHandler:
    def __init__(
        self,
        repository: AnalysisReadRepositoryPort,
        storage: StoragePort,
    ) -> None:
        self._repository = repository
        self._storage = storage

    async def handle(self, analysis_id: UUID, owner_id: UUID) -> AnalysisDetailDTO:
        summary = await self._repository.get_for_owner(analysis_id, owner_id)
        if summary is None:
            raise AnalysisNotFoundError()
        result: AnalysisResultDTO | None = None
        available = False
        if (
            summary.status in (AnalysisStatus.COMPLETED, AnalysisStatus.DEGRADED)
            and summary.report_s3_key is not None
        ):
            result = await self._load_report(summary)
            available = result is not None
        return AnalysisDetailDTO(
            id=summary.id,
            status=summary.status,
            kind=summary.document_type.value,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
            error_code=summary.error_code,
            result_available=available,
            result=result,
            progress=AnalysisProgressDTO(
                percent=summary.progress_percent,
                stage=summary.current_stage,
                detail=summary.stage_detail,
                started_at=summary.stage_started_at,
                indeterminate=summary.status in (AnalysisStatus.RUNNING, AnalysisStatus.CANCELLING),
            ),
            cancelled_at=summary.cancelled_at,
        )

    async def _load_report(self, summary: AnalysisSummary) -> AnalysisResultDTO | None:
        key = summary.report_s3_key
        if key is None:
            return None
        try:
            chunks: list[bytes] = []
            total = 0
            async for chunk in self._storage.get_stream(key):
                total += len(chunk)
                if total > _MAX_REPORT_BYTES:
                    _logger.error("analysis_report_too_large")
                    return None
                chunks.append(chunk)
            payload: object = json.loads(b"".join(chunks))
        except Exception:
            _logger.error("analysis_report_unavailable")
            return None
        return _parse_result(payload)


class ListAnalysesHandler:
    def __init__(self, repository: AnalysisReadRepositoryPort) -> None:
        self._repository = repository

    async def handle(
        self,
        owner_id: UUID,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> AnalysisListDTO:
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        before = decode_cursor(cursor) if cursor else None
        summaries = await self._repository.list_for_owner(
            owner_id,
            limit=limit + 1,
            before=before,
        )
        has_more = len(summaries) > limit
        page = summaries[:limit]
        next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if has_more and page else None
        return AnalysisListDTO(
            items=tuple(
                AnalysisListItemDTO(
                    id=summary.id,
                    status=summary.status,
                    kind=summary.document_type.value,
                    score=summary.score,
                    band=summary.band,
                    error_code=summary.error_code,
                    created_at=summary.created_at,
                    updated_at=summary.updated_at,
                )
                for summary in page
            ),
            next_cursor=next_cursor,
        )


def _parse_result(payload: object) -> AnalysisResultDTO | None:
    if not isinstance(payload, dict):
        return None
    try:
        score = int(payload["score"])
        base_score = int(payload["base_score"])
        llm_adjustment = int(payload["llm_adjustment"])
        band = RiskBand(payload["band"])
        justification = str(payload["justification"])
        evidence = tuple(_parse_evidence(item) for item in payload.get("evidence", []))
        inconsistencies = tuple(
            str(item) for item in payload.get("inconsistencies", []) if str(item).strip()
        )
        flags = tuple(str(item) for item in payload.get("degradation_flags", []))
    except (KeyError, TypeError, ValueError):
        _logger.error("analysis_report_invalid")
        return None
    if not 0 <= score <= 100 or not 0 <= base_score <= 100:
        return None
    return AnalysisResultDTO(
        score=score,
        band=band,
        base_score=base_score,
        llm_adjustment=llm_adjustment,
        evidence=evidence[:50],
        justification=justification[:4000],
        inconsistencies=inconsistencies[:5],
        degradation_flags=flags[:20],
    )


def _parse_evidence(item: object) -> AnalysisEvidenceDTO:
    if not isinstance(item, dict):
        raise ValueError("evidence must be an object")
    rule_id = item.get("rule_id")
    severity = item.get("severity")
    weight = item.get("weight")
    message_key = item.get("message_key")
    source = item.get("source")
    if not isinstance(rule_id, str):
        raise ValueError("evidence rule_id is invalid")
    if not isinstance(severity, str):
        raise ValueError("evidence severity is invalid")
    if not isinstance(message_key, str):
        raise ValueError("evidence message_key is invalid")
    if not isinstance(source, str):
        raise ValueError("evidence source is invalid")
    if not isinstance(weight, int) or isinstance(weight, bool):
        raise ValueError("evidence weight is invalid")
    return AnalysisEvidenceDTO(
        rule_id=rule_id,
        severity=severity,
        weight=weight,
        message_key=message_key,
        source=source,
    )
