import hashlib
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from io import BytesIO
from types import TracebackType
from typing import BinaryIO
from uuid import UUID, uuid4

import pytest
from pypdf import PdfWriter

from paysentineliq.application.commands.documents import (
    UploadDocumentCommand,
    UploadDocumentHandler,
)
from paysentineliq.application.errors import (
    DangerousPdfError,
    DocumentNotFoundError,
    UploadTooLargeError,
)
from paysentineliq.application.ports.document_read_repository import (
    DocumentDownloadLocation,
)
from paysentineliq.application.queries.documents import (
    DocumentDownloadUrlDTO,
    GetDocumentDownloadUrlHandler,
    GetDocumentDownloadUrlQuery,
)
from paysentineliq.domain.document import Document, DocumentKind
from paysentineliq.infrastructure.storage.inspector import (
    PdfImageDocumentInspector,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_MAX_BYTES = 1024 * 1024


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.documents: dict[UUID, Document] = {}
        self.fail_add = False

    async def add(self, document: Document) -> Document:
        if self.fail_add:
            raise RuntimeError("db unavailable")
        self.documents[document.id] = document
        return document


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.documents = FakeDocumentRepository()
        self.commits = 0

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


class FakeDocumentReadRepository:
    def __init__(self) -> None:
        self.locations: dict[tuple[UUID, UUID], str] = {}
        self.calls = 0
        self.last_call: tuple[UUID, UUID] | None = None

    async def get_download_location(
        self,
        document_id: UUID,
        owner_id: UUID,
    ) -> DocumentDownloadLocation | None:
        self.calls += 1
        self.last_call = (document_id, owner_id)
        key = self.locations.get((document_id, owner_id))
        if key is None:
            return None
        return DocumentDownloadLocation(s3_key=key)


class FakeStorage:
    def __init__(self) -> None:
        self.puts: list[tuple[str, bytes, str, dict[str, str]]] = []
        self.deletes: list[str] = []
        self.fail_put = False
        self.fail_delete = False

    async def put(
        self,
        key: str,
        stream: BinaryIO,
        *,
        content_type: str,
        size: int,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        if self.fail_put:
            raise RuntimeError("storage unavailable")
        data = stream.read()
        self.puts.append((key, data, content_type, dict(metadata or {})))

    async def get_stream(self, key: str) -> AsyncIterator[bytes]:
        yield b""

    async def delete(self, key: str) -> None:
        if self.fail_delete:
            raise RuntimeError("storage delete failed")
        self.deletes.append(key)

    async def presigned_get_url(
        self,
        key: str,
        *,
        expires_in: int,
    ) -> str:
        return f"https://storage.example/{key}?expires={expires_in}"


def _upload_handler(
    *,
    max_bytes: int = _MAX_BYTES,
) -> tuple[UploadDocumentHandler, FakeUnitOfWork, FakeStorage]:
    uow = FakeUnitOfWork()
    storage = FakeStorage()
    handler = UploadDocumentHandler(
        uow,
        storage,
        PdfImageDocumentInspector(),
        max_bytes=max_bytes,
        max_pdf_pages=5,
        clock=lambda: _NOW,
    )
    return handler, uow, storage


def _download_handler() -> tuple[
    GetDocumentDownloadUrlHandler,
    FakeDocumentReadRepository,
    FakeStorage,
]:
    read_repository = FakeDocumentReadRepository()
    storage = FakeStorage()
    handler = GetDocumentDownloadUrlHandler(
        read_repository,
        storage,
        presigned_ttl_seconds=60,
    )
    return handler, read_repository, storage


async def test_valid_upload_uses_owner_prefix_and_sanitized_metadata() -> None:
    handler, uow, storage = _upload_handler()
    owner_id = uuid4()
    pdf = _pdf_bytes()

    result = await handler.handle(
        UploadDocumentCommand(
            owner_id=owner_id,
            kind=DocumentKind.BANK_SLIP,
            original_name="../../etc/boleto.pdf",
            stream=BytesIO(pdf),
        ),
    )

    document = uow.documents.documents[result.document_id]
    assert document.s3_key == (f"users/{owner_id}/bank_slip/{result.analysis_id}/original.pdf")
    assert document.sha256 == hashlib.sha256(pdf).hexdigest()
    assert document.size == len(pdf)
    assert result.sha256 == document.sha256
    assert result.original_name_sanitized == "boleto.pdf"

    key, data, content_type, metadata = storage.puts[0]
    assert key == document.s3_key
    assert data == pdf
    assert content_type == "application/pdf"
    assert metadata["original_name"] == "boleto.pdf"
    assert metadata["analysis_id"] == str(result.analysis_id)
    assert ".." not in key


async def test_fake_pdf_extension_is_stored_as_detected_type() -> None:
    handler, _, storage = _upload_handler()
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

    result = await handler.handle(
        UploadDocumentCommand(
            owner_id=uuid4(),
            kind=DocumentKind.RECEIPT,
            original_name="fake.pdf",
            stream=BytesIO(png),
        ),
    )

    assert result.content_type == "image/png"
    assert result.original_name_sanitized == "fake.pdf"
    assert storage.puts[0][2] == "image/png"


async def test_filename_traversal_never_reaches_key() -> None:
    handler, _, _ = _upload_handler()
    owner_id = uuid4()

    result = await handler.handle(
        UploadDocumentCommand(
            owner_id=owner_id,
            kind=DocumentKind.PAYSLIP,
            original_name="..\\..\\windows\\evil.pdf",
            stream=BytesIO(_pdf_bytes()),
        ),
    )

    assert result.original_name_sanitized == "evil.pdf"


async def test_oversized_upload_is_aborted_before_storage() -> None:
    handler, uow, storage = _upload_handler(max_bytes=100)

    with pytest.raises(UploadTooLargeError):
        await handler.handle(
            UploadDocumentCommand(
                owner_id=uuid4(),
                kind=DocumentKind.RECEIPT,
                original_name="big.pdf",
                stream=BytesIO(b"\x00" * 101),
            ),
        )

    assert storage.puts == []
    assert uow.documents.documents == {}


async def test_dangerous_pdf_is_rejected_with_evidence() -> None:
    handler, _, storage = _upload_handler()
    dangerous = _pdf_bytes() + b"\n/JavaScript\n/EmbeddedFile\n"

    with pytest.raises(DangerousPdfError) as error:
        await handler.handle(
            UploadDocumentCommand(
                owner_id=uuid4(),
                kind=DocumentKind.BANK_SLIP,
                original_name="danger.pdf",
                stream=BytesIO(dangerous),
            ),
        )

    assert "javascript" in error.value.evidence
    assert "embedded_files" in error.value.evidence
    assert storage.puts == []


async def test_database_failure_compensates_stored_object() -> None:
    handler, uow, storage = _upload_handler()
    uow.documents.fail_add = True

    with pytest.raises(RuntimeError):
        await handler.handle(
            UploadDocumentCommand(
                owner_id=uuid4(),
                kind=DocumentKind.RECEIPT,
                original_name="receipt.pdf",
                stream=BytesIO(_pdf_bytes()),
            ),
        )

    assert len(storage.puts) == 1
    assert storage.deletes == [storage.puts[0][0]]


async def test_download_url_is_owner_scoped_and_uses_read_model() -> None:
    handler, read_repository, _ = _download_handler()
    owner_id = uuid4()
    document_id = uuid4()
    key = f"users/{owner_id}/receipt/{uuid4()}/original.pdf"
    read_repository.locations[(document_id, owner_id)] = key

    result = await handler.handle(
        GetDocumentDownloadUrlQuery(owner_id=owner_id, document_id=document_id),
    )

    assert result == DocumentDownloadUrlDTO(
        url=f"https://storage.example/{key}?expires=60",
        expires_in=60,
    )
    assert read_repository.calls == 1
    assert read_repository.last_call == (document_id, owner_id)

    with pytest.raises(DocumentNotFoundError):
        await handler.handle(
            GetDocumentDownloadUrlQuery(
                owner_id=uuid4(),
                document_id=document_id,
            ),
        )
