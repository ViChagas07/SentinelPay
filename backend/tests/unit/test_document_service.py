import hashlib
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from io import BytesIO
from types import TracebackType
from typing import BinaryIO
from uuid import UUID, uuid4

import pytest
from pypdf import PdfWriter

from paysentineliq.application.errors import (
    DangerousPdfError,
    DocumentNotFoundError,
    UploadTooLargeError,
)
from paysentineliq.application.use_cases.documents import DocumentService
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

    async def get_by_id_for_owner(
        self,
        document_id: UUID,
        owner_id: UUID,
    ) -> Document | None:
        document = self.documents.get(document_id)
        if document is None or document.owner_id != owner_id:
            return None
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


def _service(
    *,
    max_bytes: int = _MAX_BYTES,
) -> tuple[DocumentService, FakeUnitOfWork, FakeStorage]:
    uow = FakeUnitOfWork()
    storage = FakeStorage()
    service = DocumentService(
        uow,
        storage,
        PdfImageDocumentInspector(),
        max_bytes=max_bytes,
        max_pdf_pages=5,
        presigned_ttl_seconds=60,
        clock=lambda: _NOW,
    )
    return service, uow, storage


async def test_valid_upload_uses_owner_prefix_and_sanitized_metadata() -> None:
    service, uow, storage = _service()
    owner_id = uuid4()
    pdf = _pdf_bytes()

    uploaded = await service.upload(
        owner_id=owner_id,
        kind=DocumentKind.BANK_SLIP,
        original_name="../../etc/boleto.pdf",
        stream=BytesIO(pdf),
    )

    document = uploaded.document
    assert document.s3_key == (f"users/{owner_id}/bank_slip/{uploaded.analysis_id}/original.pdf")
    assert document.sha256 == hashlib.sha256(pdf).hexdigest()
    assert document.size == len(pdf)
    assert document.original_name_sanitized == "boleto.pdf"
    assert uow.documents.documents[document.id] == document

    key, data, content_type, metadata = storage.puts[0]
    assert key == document.s3_key
    assert data == pdf
    assert content_type == "application/pdf"
    assert metadata["original_name"] == "boleto.pdf"
    assert ".." not in key


async def test_fake_pdf_extension_is_stored_as_detected_type() -> None:
    service, _, storage = _service()
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

    uploaded = await service.upload(
        owner_id=uuid4(),
        kind=DocumentKind.RECEIPT,
        original_name="fake.pdf",
        stream=BytesIO(png),
    )

    document = uploaded.document
    assert document.s3_key.endswith("/original.png")
    assert document.content_type == "image/png"
    assert document.original_name_sanitized == "fake.pdf"
    assert storage.puts[0][2] == "image/png"


async def test_filename_traversal_never_reaches_key() -> None:
    service, _, _ = _service()
    owner_id = uuid4()

    uploaded = await service.upload(
        owner_id=owner_id,
        kind=DocumentKind.PAYSLIP,
        original_name="..\\..\\windows\\evil.pdf",
        stream=BytesIO(_pdf_bytes()),
    )

    assert "../" not in uploaded.document.s3_key
    assert "\\" not in uploaded.document.s3_key
    assert uploaded.document.s3_key.startswith(f"users/{owner_id}/")
    assert uploaded.document.original_name_sanitized == "evil.pdf"


async def test_oversized_upload_is_aborted_before_storage() -> None:
    service, uow, storage = _service(max_bytes=100)

    with pytest.raises(UploadTooLargeError):
        await service.upload(
            owner_id=uuid4(),
            kind=DocumentKind.RECEIPT,
            original_name="big.pdf",
            stream=BytesIO(b"\x00" * 101),
        )

    assert storage.puts == []
    assert uow.documents.documents == {}


async def test_dangerous_pdf_is_rejected_with_evidence() -> None:
    service, _, storage = _service()
    dangerous = _pdf_bytes() + b"\n/JavaScript\n/EmbeddedFile\n"

    with pytest.raises(DangerousPdfError) as error:
        await service.upload(
            owner_id=uuid4(),
            kind=DocumentKind.BANK_SLIP,
            original_name="danger.pdf",
            stream=BytesIO(dangerous),
        )

    assert "javascript" in error.value.evidence
    assert "embedded_files" in error.value.evidence
    assert storage.puts == []


async def test_database_failure_compensates_stored_object() -> None:
    service, uow, storage = _service()
    uow.documents.fail_add = True

    with pytest.raises(RuntimeError):
        await service.upload(
            owner_id=uuid4(),
            kind=DocumentKind.RECEIPT,
            original_name="receipt.pdf",
            stream=BytesIO(_pdf_bytes()),
        )

    assert len(storage.puts) == 1
    assert storage.deletes == [storage.puts[0][0]]


async def test_download_url_is_owner_scoped() -> None:
    service, uow, _ = _service()
    owner_id = uuid4()
    document = Document(
        id=uuid4(),
        owner_id=owner_id,
        kind=DocumentKind.RECEIPT,
        s3_key=f"users/{owner_id}/receipt/{uuid4()}/original.pdf",
        sha256="a" * 64,
        size=10,
        content_type="application/pdf",
        original_name_sanitized="receipt.pdf",
        created_at=_NOW,
    )
    uow.documents.documents[document.id] = document

    url, ttl = await service.get_download_url(
        owner_id=owner_id,
        document_id=document.id,
    )
    assert url.startswith("https://storage.example/")
    assert ttl == 60

    with pytest.raises(DocumentNotFoundError):
        await service.get_download_url(
            owner_id=uuid4(),
            document_id=document.id,
        )
