import hashlib
from io import BytesIO

import pytest
from pypdf import PdfWriter

from paysentineliq.application.errors import (
    DangerousPdfError,
    EmptyDocumentError,
    EncryptedPdfError,
    InvalidDocumentError,
    PdfPageLimitError,
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
)
from paysentineliq.application.ports.document_inspector import InspectedDocument
from paysentineliq.infrastructure.storage.inspector import (
    PdfImageDocumentInspector,
)

pytestmark = pytest.mark.unit

_MAX_BYTES = 10 * 1024 * 1024


def _pdf_bytes(*, pages: int = 1, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    if encrypted:
        writer.encrypt("secret")
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


async def _inspect(
    data: bytes,
    *,
    max_bytes: int = _MAX_BYTES,
    max_pages: int = 50,
) -> InspectedDocument:
    return await PdfImageDocumentInspector().inspect(
        BytesIO(data),
        max_bytes=max_bytes,
        max_pdf_pages=max_pages,
    )


async def test_valid_pdf_is_detected_and_hashed() -> None:
    data = _pdf_bytes(pages=2)

    result = await _inspect(data)

    assert result.extension == "pdf"
    assert result.content_type == "application/pdf"
    assert result.size == len(data)
    assert result.sha256 == hashlib.sha256(data).hexdigest()
    assert result.page_count == 2


async def test_png_and_jpeg_are_detected_by_magic_bytes() -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 16

    png_result = await _inspect(png)
    jpeg_result = await _inspect(jpeg)

    assert png_result.extension == "png"
    assert png_result.content_type == "image/png"
    assert png_result.page_count is None
    assert jpeg_result.extension == "jpg"
    assert jpeg_result.content_type == "image/jpeg"


async def test_empty_file_is_rejected() -> None:
    with pytest.raises(EmptyDocumentError):
        await _inspect(b"")


async def test_unknown_content_is_rejected() -> None:
    with pytest.raises(UnsupportedDocumentTypeError):
        await _inspect(b"plain text pretending to be a document")


async def test_pdf_over_page_limit_is_rejected() -> None:
    with pytest.raises(PdfPageLimitError):
        await _inspect(_pdf_bytes(pages=2), max_pages=1)


async def test_encrypted_pdf_is_rejected() -> None:
    with pytest.raises(EncryptedPdfError):
        await _inspect(_pdf_bytes(encrypted=True))


async def test_invalid_pdf_is_rejected() -> None:
    with pytest.raises(InvalidDocumentError):
        await _inspect(b"%PDF-1.4\nthis is not a valid pdf")


async def test_pdf_with_active_content_reports_evidence() -> None:
    data = _pdf_bytes() + b"\n/JavaScript\n/EmbeddedFile\n"

    with pytest.raises(DangerousPdfError) as error:
        await _inspect(data)

    assert "javascript" in error.value.evidence
    assert "embedded_files" in error.value.evidence


class TrackingBytesIO(BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.total_read = 0

    def read(self, size: int | None = -1) -> bytes:
        chunk = super().read(size)
        self.total_read += len(chunk)
        return chunk


async def test_size_limit_aborts_without_reading_entire_stream() -> None:
    stream = TrackingBytesIO(b"\x00" * 1_000_000)

    with pytest.raises(UploadTooLargeError):
        await PdfImageDocumentInspector().inspect(
            stream,
            max_bytes=1_000,
            max_pdf_pages=50,
        )

    assert stream.total_read < 1_000_000
