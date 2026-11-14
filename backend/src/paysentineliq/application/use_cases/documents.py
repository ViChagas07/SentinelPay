import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID, uuid4

from paysentineliq.application.errors import (
    DocumentNotFoundError,
    InvalidDocumentError,
)
from paysentineliq.application.ports.document_inspector import DocumentInspector
from paysentineliq.application.ports.document_unit_of_work import (
    DocumentUnitOfWork,
)
from paysentineliq.application.ports.storage import StoragePort
from paysentineliq.application.security.storage_keys import (
    build_original_key,
    sanitize_filename,
)
from paysentineliq.domain.document import Document, DocumentKind

_logger = logging.getLogger("paysentineliq")


@dataclass(frozen=True, slots=True)
class UploadedDocument:
    document: Document
    analysis_id: UUID


class DocumentService:
    def __init__(
        self,
        unit_of_work: DocumentUnitOfWork,
        storage: StoragePort,
        inspector: DocumentInspector,
        *,
        max_bytes: int,
        max_pdf_pages: int,
        presigned_ttl_seconds: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        if max_pdf_pages <= 0:
            raise ValueError("max_pdf_pages must be positive")
        if presigned_ttl_seconds <= 0:
            raise ValueError("presigned_ttl_seconds must be positive")
        self._unit_of_work = unit_of_work
        self._storage = storage
        self._inspector = inspector
        self._max_bytes = max_bytes
        self._max_pdf_pages = max_pdf_pages
        self._presigned_ttl = presigned_ttl_seconds
        self._clock = clock or (lambda: datetime.now(UTC))

    async def upload(
        self,
        *,
        owner_id: UUID,
        kind: DocumentKind,
        original_name: str | None,
        stream: BinaryIO,
    ) -> UploadedDocument:
        inspected = await self._inspector.inspect(
            stream,
            max_bytes=self._max_bytes,
            max_pdf_pages=self._max_pdf_pages,
        )

        analysis_id = uuid4()
        key = build_original_key(
            owner_id=owner_id,
            kind=kind,
            analysis_id=analysis_id,
            extension=inspected.extension,
        )
        sanitized_name = sanitize_filename(original_name)
        document = Document(
            id=uuid4(),
            owner_id=owner_id,
            kind=kind,
            s3_key=key,
            sha256=inspected.sha256,
            size=inspected.size,
            content_type=inspected.content_type,
            original_name_sanitized=sanitized_name,
            created_at=self._clock(),
        )

        try:
            stream.seek(0)
        except OSError as exc:
            raise InvalidDocumentError() from exc

        await self._storage.put(
            key,
            stream,
            content_type=inspected.content_type,
            size=inspected.size,
            metadata={
                "sha256": inspected.sha256,
                "kind": kind.value,
                "analysis_id": str(analysis_id),
                "original_name": sanitized_name,
            },
        )

        try:
            async with self._unit_of_work as uow:
                stored = await uow.documents.add(document)
                await uow.commit()
        except Exception:
            try:
                await self._storage.delete(key)
            except Exception:
                _logger.error("storage_compensation_failed")
            raise

        return UploadedDocument(document=stored, analysis_id=analysis_id)

    async def get_download_url(
        self,
        *,
        owner_id: UUID,
        document_id: UUID,
    ) -> tuple[str, int]:
        async with self._unit_of_work as uow:
            document = await uow.documents.get_by_id_for_owner(
                document_id,
                owner_id,
            )

        if document is None:
            raise DocumentNotFoundError()

        url = await self._storage.presigned_get_url(
            document.s3_key,
            expires_in=self._presigned_ttl,
        )
        return url, self._presigned_ttl
