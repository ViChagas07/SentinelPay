from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile
from pydantic import BaseModel

from paysentineliq.application.commands.create_analysis import (
    CreateAnalysisCommand,
    CreateAnalysisHandler,
)
from paysentineliq.application.queries.analyses import (
    AnalysisDetailDTO,
    AnalysisResultDTO,
    GetAnalysisHandler,
    ListAnalysesHandler,
)
from paysentineliq.domain.document import DocumentKind
from paysentineliq.domain.user import User
from paysentineliq.interface.api.dependencies import (
    get_analysis_detail_query,
    get_analysis_list_query,
    get_create_analysis_handler,
    get_current_user,
    get_locale,
)

router = APIRouter(prefix="/analyses", tags=["analyses"])


class AnalysisKind(StrEnum):
    BOLETO = "boleto"
    PAYSLIP = "payslip"


_DOCUMENT_KIND = {
    AnalysisKind.BOLETO: DocumentKind.BANK_SLIP,
    AnalysisKind.PAYSLIP: DocumentKind.PAYSLIP,
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


class AnalysisDetailResponse(BaseModel):
    id: UUID
    status: str
    kind: str
    created_at: datetime
    updated_at: datetime
    error_code: str | None
    result_available: bool
    result: AnalysisResultResponse | None


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
