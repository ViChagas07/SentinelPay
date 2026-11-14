from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Response, UploadFile
from pydantic import BaseModel

from paysentineliq.application.commands.create_analysis import (
    CreateAnalysisCommand,
    CreateAnalysisHandler,
)
from paysentineliq.domain.document import DocumentKind
from paysentineliq.domain.user import User
from paysentineliq.interface.api.dependencies import (
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
