from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from paysentineliq.application.commands.documents import (
    UploadDocumentCommand,
    UploadDocumentHandler,
)
from paysentineliq.application.queries.documents import (
    GetDocumentDownloadUrlHandler,
    GetDocumentDownloadUrlQuery,
)
from paysentineliq.domain.document import DocumentKind
from paysentineliq.domain.user import User
from paysentineliq.interface.api.dependencies import (
    get_current_user,
    get_document_download_query,
    get_upload_document_handler,
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
    handler: Annotated[UploadDocumentHandler, Depends(get_upload_document_handler)],
    kind: Annotated[DocumentKind, Form()],
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    result = await handler.handle(
        UploadDocumentCommand(
            owner_id=user.id,
            kind=kind,
            original_name=file.filename,
            stream=file.file,
        ),
    )
    return DocumentResponse(
        id=result.document_id,
        analysis_id=result.analysis_id,
        kind=result.kind.value,
        sha256=result.sha256,
        size=result.size,
        content_type=result.content_type,
        original_name_sanitized=result.original_name_sanitized,
        created_at=result.created_at,
    )


@router.get("/{document_id}/url", response_model=DocumentUrlResponse)
async def document_download_url(
    document_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[
        GetDocumentDownloadUrlHandler,
        Depends(get_document_download_query),
    ],
) -> DocumentUrlResponse:
    result = await handler.handle(
        GetDocumentDownloadUrlQuery(
            owner_id=user.id,
            document_id=document_id,
        ),
    )
    return DocumentUrlResponse(url=result.url, expires_in=result.expires_in)
