import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from paysentineliq.application.commands.cancel_analysis import (
    AnalysisCancellationDTO,
    CancelAnalysisHandler,
)
from paysentineliq.application.commands.create_analysis import (
    CreateAnalysisCommand,
    CreateAnalysisHandler,
)
from paysentineliq.application.errors import AnalysisNotFoundError
from paysentineliq.application.ports.analysis_read_repository import (
    AnalysisReadRepositoryPort,
    AnalysisSummary,
)
from paysentineliq.application.queries.analyses import (
    AnalysisDetailDTO,
    AnalysisProgressDTO,
    AnalysisResultDTO,
    GetAnalysisHandler,
    ListAnalysesHandler,
)
from paysentineliq.domain.analysis import AnalysisStatus
from paysentineliq.domain.document import DocumentKind
from paysentineliq.domain.user import User
from paysentineliq.interface.api.dependencies import (
    get_analysis_detail_query,
    get_analysis_list_query,
    get_analysis_read_repository,
    get_cancel_analysis_handler,
    get_create_analysis_handler,
    get_current_user,
    get_locale,
)

router = APIRouter(prefix="/analyses", tags=["analyses"])


class AnalysisKind(StrEnum):
    BOLETO = "boleto"
    PAYSLIP = "payslip"
    RECEIPT = "receipt"


_DOCUMENT_KIND = {
    AnalysisKind.BOLETO: DocumentKind.BANK_SLIP,
    AnalysisKind.PAYSLIP: DocumentKind.PAYSLIP,
    AnalysisKind.RECEIPT: DocumentKind.RECEIPT,
}


class CreateAnalysisResponse(BaseModel):
    analysis_id: UUID
    status: str


class EvidenceResponse(BaseModel):
    rule_id: str
    severity: str
    weight: int
    message_key: str
    source: str


class AnalysisResultResponse(BaseModel):
    score: int
    band: str
    base_score: int
    llm_adjustment: int
    evidence: list[EvidenceResponse]
    justification: str
    inconsistencies: list[str]
    degradation_flags: list[str]


class AnalysisProgressResponse(BaseModel):
    percent: int
    stage: str | None
    detail: str | None
    started_at: datetime | None
    indeterminate: bool


class AnalysisDetailResponse(BaseModel):
    id: UUID
    status: str
    kind: str
    created_at: datetime
    updated_at: datetime
    error_code: str | None
    result_available: bool
    result: AnalysisResultResponse | None
    progress: AnalysisProgressResponse
    cancelled_at: datetime | None


class AnalysisProgressEventResponse(BaseModel):
    id: UUID
    status: str
    kind: str
    created_at: datetime
    updated_at: datetime
    error_code: str | None
    result_available: bool
    progress: AnalysisProgressResponse
    cancelled_at: datetime | None


class CancelAnalysisResponse(BaseModel):
    analysis_id: UUID
    status: str


class AnalysisListItemResponse(BaseModel):
    id: UUID
    status: str
    kind: str
    score: int | None
    band: str | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class AnalysisListResponse(BaseModel):
    items: list[AnalysisListItemResponse]
    next_cursor: str | None


@router.post("", response_model=CreateAnalysisResponse, status_code=202)
async def create_analysis(
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[CreateAnalysisHandler, Depends(get_create_analysis_handler)],
    response: Response,
    kind: Annotated[AnalysisKind, Form()],
    file: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    locale: Annotated[str, Depends(get_locale)] = "pt",
) -> CreateAnalysisResponse:
    result = await handler.handle(
        CreateAnalysisCommand(
            owner_id=user.id,
            kind=_DOCUMENT_KIND[kind],
            original_name=file.filename,
            stream=file.file,
            idempotency_key=idempotency_key,
            locale=locale,
        ),
    )
    if result.replayed:
        response.headers["Idempotency-Replayed"] = "true"
    return CreateAnalysisResponse(
        analysis_id=result.analysis_id,
        status=result.status.value,
    )


@router.get("", response_model=AnalysisListResponse)
async def list_analyses(
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[ListAnalysesHandler, Depends(get_analysis_list_query)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> AnalysisListResponse:
    result = await handler.handle(user.id, limit=limit, cursor=cursor)
    return AnalysisListResponse(
        items=[
            AnalysisListItemResponse(
                id=item.id,
                status=item.status.value,
                kind=item.kind,
                score=item.score,
                band=item.band.value if item.band is not None else None,
                error_code=item.error_code,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in result.items
        ],
        next_cursor=result.next_cursor,
    )


@router.get("/{analysis_id}", response_model=AnalysisDetailResponse)
async def get_analysis(
    analysis_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[GetAnalysisHandler, Depends(get_analysis_detail_query)],
) -> AnalysisDetailResponse:
    detail = await handler.handle(analysis_id, user.id)
    return _detail_response(detail)


def _detail_response(detail: AnalysisDetailDTO) -> AnalysisDetailResponse:
    return AnalysisDetailResponse(
        id=detail.id,
        status=detail.status.value,
        kind=detail.kind,
        created_at=detail.created_at,
        updated_at=detail.updated_at,
        error_code=detail.error_code,
        result_available=detail.result_available,
        result=_result_response(detail.result),
        progress=_progress_response(detail.progress),
        cancelled_at=detail.cancelled_at,
    )


def _progress_response(progress: AnalysisProgressDTO) -> AnalysisProgressResponse:
    return AnalysisProgressResponse(
        percent=progress.percent,
        stage=progress.stage.value if progress.stage is not None else None,
        detail=progress.detail,
        started_at=progress.started_at,
        indeterminate=progress.indeterminate,
    )


def _progress_event(summary: AnalysisSummary) -> AnalysisProgressEventResponse:
    return AnalysisProgressEventResponse(
        id=summary.id,
        status=summary.status.value,
        kind=summary.document_type.value,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        error_code=summary.error_code,
        result_available=summary.report_s3_key is not None
        and summary.status in (AnalysisStatus.COMPLETED, AnalysisStatus.DEGRADED),
        progress=AnalysisProgressResponse(
            percent=summary.progress_percent,
            stage=summary.current_stage.value if summary.current_stage is not None else None,
            detail=summary.stage_detail,
            started_at=summary.stage_started_at,
            indeterminate=summary.status in (AnalysisStatus.RUNNING, AnalysisStatus.CANCELLING),
        ),
        cancelled_at=summary.cancelled_at,
    )


def _is_terminal(status: AnalysisStatus) -> bool:
    return status in (
        AnalysisStatus.COMPLETED,
        AnalysisStatus.DEGRADED,
        AnalysisStatus.FAILED,
        AnalysisStatus.CANCELLED,
    )


@router.post(
    "/{analysis_id}/cancel",
    response_model=CancelAnalysisResponse,
    status_code=202,
)
async def cancel_analysis(
    analysis_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[CancelAnalysisHandler, Depends(get_cancel_analysis_handler)],
) -> CancelAnalysisResponse:
    result: AnalysisCancellationDTO = await handler.handle(analysis_id, user.id)
    return CancelAnalysisResponse(
        analysis_id=result.analysis_id,
        status=result.status.value,
    )


@router.get("/{analysis_id}/events")
async def analysis_events(
    analysis_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[
        AnalysisReadRepositoryPort,
        Depends(get_analysis_read_repository),
    ],
    request: Request,
) -> StreamingResponse:
    summary = await repository.get_for_owner(analysis_id, user.id)
    if summary is None:
        raise AnalysisNotFoundError()

    async def stream() -> "AsyncIterator[str]":
        last_signature: tuple[object, ...] | None = None
        heartbeat = 0
        while True:
            if await request.is_disconnected():
                break
            current = await repository.get_for_owner(analysis_id, user.id)
            if current is None:
                break
            signature = (
                current.status.value,
                current.progress_percent,
                current.current_stage,
                current.stage_detail,
                current.updated_at,
                current.error_code,
                current.cancelled_at,
            )
            payload = _progress_event(current)
            data = payload.model_dump_json()
            if signature != last_signature:
                last_signature = signature
                yield f"event: progress\ndata: {data}\n\n"
            if _is_terminal(current.status):
                yield f"event: done\ndata: {data}\n\n"
                break
            heartbeat += 1
            if heartbeat >= 20:
                heartbeat = 0
                yield ": ping\n\n"
            await asyncio.sleep(0.75)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _result_response(result: AnalysisResultDTO | None) -> AnalysisResultResponse | None:
    if result is None:
        return None
    return AnalysisResultResponse(
        score=result.score,
        band=result.band.value,
        base_score=result.base_score,
        llm_adjustment=result.llm_adjustment,
        evidence=[
            EvidenceResponse(
                rule_id=item.rule_id,
                severity=item.severity,
                weight=item.weight,
                message_key=item.message_key,
                source=item.source,
            )
            for item in result.evidence
        ],
        justification=result.justification,
        inconsistencies=list(result.inconsistencies),
        degradation_flags=list(result.degradation_flags),
    )
