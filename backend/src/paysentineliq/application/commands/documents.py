import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID, uuid4

from paysentineliq.application.errors import InvalidDocumentError
from paysentineliq.application.ports.document_inspector import (
    DocumentInspector,
    InspectedDocument,
)
from paysentineliq.application.ports.document_unit_of_work import DocumentUnitOfWork
from paysentineliq.application.ports.storage import StoragePort
from paysentineliq.application.security.storage_keys import (
    build_original_key,
    sanitize_filename,
)
from paysentineliq.domain.document import Document, DocumentKind

_logger = logging.getLogger("paysentineliq")


@dataclass(frozen=True, slots=True)
class UploadDocumentCommand:
    owner_id: UUID
    kind: DocumentKind
    original_name: str | None
    stream: BinaryIO


@dataclass(frozen=True, slots=True)
class UploadedDocumentResult:
    document_id: UUID
    analysis_id: UUID
    kind: DocumentKind
    sha256: str
    size: int
    content_type: str
    original_name_sanitized: str
    created_at: datetime


class DocumentPreparer:
    def __init__(
        self,
        storage: StoragePort,
        inspector: DocumentInspector,
        *,
        max_bytes: int,
        max_pdf_pages: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        if max_pdf_pages <= 0:
            raise ValueError("max_pdf_pages must be positive")
        self._storage = storage
        self._inspector = inspector
        self._max_bytes = max_bytes
        self._max_pdf_pages = max_pdf_pages
        self._clock = clock or (lambda: datetime.now(UTC))

    async def inspect(self, stream: BinaryIO) -> InspectedDocument:
        return await self._inspector.inspect(
            stream,
            max_bytes=self._max_bytes,
            max_pdf_pages=self._max_pdf_pages,
        )

    async def discard(self, s3_key: str) -> None:
        await self._storage.delete(s3_key)

    async def prepare(
        self,
        *,
        owner_id: UUID,
        kind: DocumentKind,
        original_name: str | None,
        stream: BinaryIO,
        analysis_id: UUID,
        inspected: InspectedDocument | None = None,
    ) -> Document:
        if inspected is None:
            inspected = await self.inspect(stream)
        key = build_original_key(
            owner_id=owner_id,
            kind=kind,
            analysis_id=analysis_id,
            extension=inspected.extension,
        )
        sanitized_name = sanitize_filename(original_name)
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
        return Document(
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


class UploadDocumentHandler:
    def __init__(
        self,
        unit_of_work: DocumentUnitOfWork,
        storage: StoragePort,
        inspector: DocumentInspector,
        *,
        max_bytes: int,
        max_pdf_pages: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._storage = storage
        self._preparer = DocumentPreparer(
            storage,
            inspector,
            max_bytes=max_bytes,
            max_pdf_pages=max_pdf_pages,
            clock=clock,
        )

    async def handle(self, command: UploadDocumentCommand) -> UploadedDocumentResult:
        analysis_id = uuid4()
        document = await self._preparer.prepare(
            owner_id=command.owner_id,
            kind=command.kind,
            original_name=command.original_name,
            stream=command.stream,
            analysis_id=analysis_id,
        )

        try:
            async with self._unit_of_work as uow:
                stored = await uow.documents.add(document)
                await uow.commit()
        except Exception:
            try:
                await self._storage.delete(document.s3_key)
            except Exception:
                _logger.error("storage_compensation_failed")
            raise

        return UploadedDocumentResult(
            document_id=stored.id,
            analysis_id=analysis_id,
            kind=stored.kind,
            sha256=stored.sha256,
            size=stored.size,
            content_type=stored.content_type,
            original_name_sanitized=stored.original_name_sanitized,
            created_at=stored.created_at,
        )
