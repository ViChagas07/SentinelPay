import asyncio
import struct
import zlib
from types import SimpleNamespace
from typing import Any

import cv2
import pymupdf
import pytest

from paysentineliq.application.errors import (
    InvalidDocumentError,
    OcrImageTooLargeError,
    OcrPageLimitError,
    OcrTimeoutError,
    UnsupportedDocumentError,
)
from paysentineliq.application.ports.ocr import OcrBlock, OcrResult
from paysentineliq.infrastructure.ingestion.service import (
    DocumentIngestionService,
)
from paysentineliq.infrastructure.vision.visual_anomalies import (
    VisualAnomalyService,
)
from tests.support.synthetic import (
    clean_image_bytes,
    native_pdf_bytes,
    scanned_pdf_bytes,
)

pytestmark = pytest.mark.unit


class FakeOcr:
    def __init__(
        self,
        *,
        language: str = "pt",
        delay: float = 0.0,
        text: str = "OCR TEXT",
    ) -> None:
        self.language = language
        self.delay = delay
        self.text = text
        self.calls = 0

    async def recognize(
        self,
        image: bytes,
        *,
        language: str | None = None,
    ) -> OcrResult:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return OcrResult(
            blocks=(
                OcrBlock(
                    text=self.text,
                    bbox=(1.0, 2.0, 3.0, 4.0),
                    confidence=0.88,
                ),
            ),
            language=language or self.language,
        )


def _service(
    ocr: FakeOcr,
    *,
    max_pages: int = 5,
    timeout_seconds: float = 1.0,
    max_image_pixels: int = 25_000_000,
) -> DocumentIngestionService:
    return DocumentIngestionService(
        ocr,
        VisualAnomalyService(),
        languages=("pt",),
        max_pages=max_pages,
        render_dpi=100,
        timeout_seconds=timeout_seconds,
        max_image_pixels=max_image_pixels,
        native_min_chars=40,
    )


async def test_native_pdf_uses_text_layer_without_ocr() -> None:
    ocr = FakeOcr()
    result = await _service(ocr).ingest(native_pdf_bytes(pages=2))

    assert result.used_ocr is False
    assert result.source_type == "pdf_native"
    assert result.page_count == 2
    assert result.language is None
    assert {block.page for block in result.blocks} == {1, 2}
    assert any("SYNTHETIC PDF" in block.text for block in result.blocks)
    assert ocr.calls == 0
    assert "pdf_producer" in {signal.name for signal in result.signals}
    assert "image_blur" in {signal.name for signal in result.signals}


async def test_scanned_pdf_uses_ocr() -> None:
    ocr = FakeOcr(language="es")
    result = await _service(ocr).ingest(scanned_pdf_bytes())

    assert result.used_ocr is True
    assert result.source_type == "pdf_ocr"
    assert result.page_count == 1
    assert result.language == "pt"
    assert result.blocks[0].text == "OCR TEXT"
    assert result.blocks[0].page == 1
    assert ocr.calls == 1


async def test_image_uses_ocr() -> None:
    ocr = FakeOcr()
    result = await _service(ocr).ingest(clean_image_bytes(800, 600))

    assert result.used_ocr is True
    assert result.source_type == "image"
    assert result.page_count == 1
    assert result.blocks[0].page == 1
    assert result.blocks[0].confidence == pytest.approx(0.88)
    assert result.blocks[0].bbox == (1.0, 2.0, 3.0, 4.0)
    assert ocr.calls == 1


async def test_page_limit_is_enforced_before_ocr() -> None:
    ocr = FakeOcr()

    with pytest.raises(OcrPageLimitError):
        await _service(ocr, max_pages=1).ingest(native_pdf_bytes(pages=2))

    assert ocr.calls == 0


async def test_image_pixel_limit_is_enforced() -> None:
    ocr = FakeOcr()

    with pytest.raises(OcrImageTooLargeError):
        await _service(ocr, max_image_pixels=10).ingest(clean_image_bytes(800, 600))

    assert ocr.calls == 0


async def test_image_pixel_limit_is_checked_before_decoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original = cv2.imdecode

    def spy(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(cv2, "imdecode", spy)
    ocr = FakeOcr()

    with pytest.raises(OcrImageTooLargeError):
        await _service(ocr, max_image_pixels=10).ingest(clean_image_bytes(800, 600))

    assert calls == 0
    assert ocr.calls == 0


async def test_decompression_bomb_image_is_rejected_by_header() -> None:
    ocr = FakeOcr()

    with pytest.raises(OcrImageTooLargeError):
        await _service(ocr, max_image_pixels=25_000_000).ingest(
            _png_with_dimensions(6000, 6000),
        )

    assert ocr.calls == 0


class _OversizedPage:
    rect = SimpleNamespace(width=1000.0, height=1000.0)

    def get_text(self, kind: str) -> list[object]:
        return []

    def get_pixmap(self, **kwargs: object) -> object:
        raise AssertionError("page must not be rendered before the size check")


class _OversizedDocument:
    page_count = 1

    def load_page(self, index: int) -> _OversizedPage:
        return _OversizedPage()

    def close(self) -> None:
        return None


async def test_pdf_page_pixel_limit_is_checked_before_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = native_pdf_bytes()
    monkeypatch.setattr(
        VisualAnomalyService,
        "analyze_pdf_metadata",
        lambda self, data: (),
    )
    monkeypatch.setattr(pymupdf, "open", lambda *args, **kwargs: _OversizedDocument())
    ocr = FakeOcr()

    with pytest.raises(OcrImageTooLargeError):
        await _service(ocr, max_image_pixels=10).ingest(pdf)

    assert ocr.calls == 0


def _png_with_dimensions(width: int, height: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    header_chunk = (
        struct.pack(">I", len(header))
        + b"IHDR"
        + header
        + struct.pack(">I", zlib.crc32(b"IHDR" + header) & 0xFFFFFFFF)
    )
    end_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    return signature + header_chunk + end_chunk


async def test_ocr_timeout_is_controlled() -> None:
    ocr = FakeOcr(delay=0.2)

    with pytest.raises(OcrTimeoutError):
        await _service(ocr, timeout_seconds=0.01).ingest(clean_image_bytes(800, 600))

    assert ocr.calls == 1


async def test_unreadable_documents_fail_with_controlled_errors() -> None:
    ocr = FakeOcr()
    service = _service(ocr)

    with pytest.raises(UnsupportedDocumentError):
        await service.ingest(b"not a document")
    with pytest.raises(InvalidDocumentError):
        await service.ingest(b"\x89PNG\r\n\x1a\n")
    assert ocr.calls == 0
