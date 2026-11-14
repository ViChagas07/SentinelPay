import asyncio
import hashlib
from typing import BinaryIO

from pypdf import PdfReader

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

_PDF_SIGNATURE = b"%PDF-"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_CHUNK_SIZE = 64 * 1024
_MARKERS: tuple[tuple[str, tuple[bytes, ...]], ...] = (
    ("javascript", (b"/JavaScript", b"/JS")),
    ("embedded_files", (b"/EmbeddedFile", b"/EmbeddedFiles", b"/Filespec")),
    ("launch_actions", (b"/Launch",)),
)


class PdfImageDocumentInspector:
    async def inspect(
        self,
        stream: BinaryIO,
        *,
        max_bytes: int,
        max_pdf_pages: int,
    ) -> InspectedDocument:
        return await asyncio.to_thread(
            self._inspect_sync,
            stream,
            max_bytes,
            max_pdf_pages,
        )

    def _inspect_sync(
        self,
        stream: BinaryIO,
        max_bytes: int,
        max_pdf_pages: int,
    ) -> InspectedDocument:
        stream.seek(0)
        digest = hashlib.sha256()
        size = 0
        prefix = b""
        tail = b""
        evidence: set[str] = set()

        while True:
            chunk = stream.read(_CHUNK_SIZE)
            if not chunk:
                break
            if not isinstance(chunk, bytes):
                raise InvalidDocumentError()

            size += len(chunk)
            if size > max_bytes:
                raise UploadTooLargeError()

            digest.update(chunk)
            if len(prefix) < 16:
                prefix += chunk[: 16 - len(prefix)]

            window = tail + chunk
            for label, markers in _MARKERS:
                if any(marker in window for marker in markers):
                    evidence.add(label)
            tail = window[-64:]

        if size == 0:
            raise EmptyDocumentError()

        extension, content_type = _detect(prefix)

        if extension == "pdf":
            if evidence:
                raise DangerousPdfError(tuple(sorted(evidence)))
            page_count = _count_pdf_pages(stream, max_pdf_pages)
        else:
            page_count = None

        return InspectedDocument(
            extension=extension,
            content_type=content_type,
            size=size,
            sha256=digest.hexdigest(),
            page_count=page_count,
        )


def _detect(prefix: bytes) -> tuple[str, str]:
    if prefix.startswith(_PDF_SIGNATURE):
        return "pdf", "application/pdf"
    if prefix.startswith(_PNG_SIGNATURE):
        return "png", "image/png"
    if prefix.startswith(_JPEG_SIGNATURE):
        return "jpg", "image/jpeg"
    raise UnsupportedDocumentTypeError()


def _count_pdf_pages(stream: BinaryIO, max_pdf_pages: int) -> int:
    stream.seek(0)
    try:
        reader = PdfReader(stream)
        if reader.is_encrypted:
            raise EncryptedPdfError()
        pages = len(reader.pages)
    except EncryptedPdfError:
        raise
    except Exception as exc:
        raise InvalidDocumentError() from exc

    if pages == 0:
        raise InvalidDocumentError()
    if pages > max_pdf_pages:
        raise PdfPageLimitError()
    return pages
