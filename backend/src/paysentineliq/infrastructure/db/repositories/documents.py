from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paysentineliq.application.ports.document_read_repository import (
    DocumentDownloadLocation,
)
from paysentineliq.domain.document import Document, DocumentKind
from paysentineliq.infrastructure.db.models import DocumentModel


class SqlAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: Document) -> Document:
        model = DocumentModel(
            id=document.id,
            owner_id=document.owner_id,
            kind=document.kind.value,
            s3_key=document.s3_key,
            sha256=document.sha256,
            size=document.size,
            content_type=document.content_type,
            original_name_sanitized=document.original_name_sanitized,
            created_at=document.created_at,
            updated_at=document.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def get_by_id_for_owner(
        self,
        document_id: UUID,
        owner_id: UUID,
    ) -> Document | None:
        model = await self._session.scalar(
            select(DocumentModel).where(
                DocumentModel.id == document_id,
                DocumentModel.owner_id == owner_id,
            )
        )
        return _to_domain(model) if model is not None else None


class SqlAlchemyDocumentReadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_download_location(
        self,
        document_id: UUID,
        owner_id: UUID,
    ) -> DocumentDownloadLocation | None:
        s3_key = await self._session.scalar(
            select(DocumentModel.s3_key).where(
                DocumentModel.id == document_id,
                DocumentModel.owner_id == owner_id,
            ),
        )
        if s3_key is None:
            return None
        return DocumentDownloadLocation(s3_key=s3_key)


def _to_domain(model: DocumentModel) -> Document:
    return Document(
        id=model.id,
        owner_id=model.owner_id,
        kind=DocumentKind(model.kind),
        s3_key=model.s3_key,
        sha256=model.sha256,
        size=model.size,
        content_type=model.content_type,
        original_name_sanitized=model.original_name_sanitized,
        created_at=model.created_at,
    )


def utc_now() -> datetime:
    return datetime.now(UTC)
