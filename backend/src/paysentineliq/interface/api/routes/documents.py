from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from paysentineliq.application.use_cases.documents import DocumentService
from paysentineliq.domain.document import DocumentKind
from paysentineliq.domain.user import User
from paysentineliq.interface.api.dependencies import (
    get_current_user,
    get_document_service,
)

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    id: UUID
    analysis_id: UUID
    kind: str
    sha256: str
    size: int
    content_type: str
    original_name_sanitized: str
    created_at: datetime


class DocumentUrlResponse(BaseModel):
    url: str
    expires_in: int


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=201,
)
async def upload_document(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    kind: Annotated[DocumentKind, Form()],
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    uploaded = await service.upload(
        owner_id=user.id,
        kind=kind,
        original_name=file.filename,
        stream=file.file,
    )
    document = uploaded.document
    return DocumentResponse(
        id=document.id,
        analysis_id=uploaded.analysis_id,
        kind=document.kind.value,
        sha256=document.sha256,
        size=document.size,
        content_type=document.content_type,
        original_name_sanitized=document.original_name_sanitized,
        created_at=document.created_at,
    )


@router.get("/{document_id}/url", response_model=DocumentUrlResponse)
async def document_download_url(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentUrlResponse:
    url, expires_in = await service.get_download_url(
        owner_id=user.id,
        document_id=document_id,
    )
    return DocumentUrlResponse(url=url, expires_in=expires_in)
