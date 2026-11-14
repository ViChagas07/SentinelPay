import asyncio

import cv2
import numpy as np
import pymupdf

from paysentineliq.application.errors import (
    InvalidDocumentError,
    OcrImageTooLargeError,
    OcrPageLimitError,
    OcrTimeoutError,
    UnsupportedDocumentError,
)
from paysentineliq.application.ports.ocr import OcrPort, OcrResult
from paysentineliq.domain.ingestion import (
    BBox,
    IngestionResult,
    TextBlock,
    VisualSignal,
)
from paysentineliq.infrastructure.vision.visual_anomalies import (
    VisualAnomalyService,
)

_PDF_SIGNATURE = b"%PDF-"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"


class DocumentIngestionService:
    def __init__(
        self,
        ocr: OcrPort,
        visuals: VisualAnomalyService,
        *,
        languages: tuple[str, ...],
        max_pages: int,
        render_dpi: int,
        timeout_seconds: float,
        max_image_pixels: int,
        native_min_chars: int,
    ) -> None:
        if not languages:
            raise ValueError("languages must not be empty")
        if max_pages <= 0:
            raise ValueError("max_pages must be positive")
        if render_dpi <= 0:
            raise ValueError("render_dpi must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_image_pixels <= 0:
            raise ValueError("max_image_pixels must be positive")
        if native_min_chars < 0:
            raise ValueError("native_min_chars must be non-negative")

        self._ocr = ocr
        self._visuals = visuals
        self._languages = languages
        self._max_pages = max_pages
        self._render_dpi = render_dpi
        self._timeout = timeout_seconds
        self._max_image_pixels = max_image_pixels
        self._native_min_chars = native_min_chars

    async def ingest(self, data: bytes) -> IngestionResult:
        if not data:
            raise InvalidDocumentError()
        if data.startswith(_PDF_SIGNATURE):
            return await self._ingest_pdf(data)
        if data.startswith(_PNG_SIGNATURE) or data.startswith(_JPEG_SIGNATURE):
            return await self._ingest_image(data)
        raise UnsupportedDocumentError()

    async def _ingest_image(self, data: bytes) -> IngestionResult:
        self._ensure_image_size(data)

        ocr_result = await self._run_ocr(data)
        image_signals = await asyncio.to_thread(
            self._visuals.analyze_image,
            data,
            page=1,
        )
        blocks = tuple(
            TextBlock(
                text=block.text,
                page=1,
                bbox=block.bbox,
                confidence=block.confidence,
            )
            for block in ocr_result.blocks
        )
        return IngestionResult(
            blocks=blocks,
            signals=tuple(image_signals),
            page_count=1,
            used_ocr=True,
            source_type="image",
            language=ocr_result.language,
        )

    async def _ingest_pdf(self, data: bytes) -> IngestionResult:
        try:
            document = await asyncio.to_thread(
                pymupdf.open,
                stream=data,
                filetype="pdf",
            )
        except Exception as exc:
            raise InvalidDocumentError() from exc

        try:
            page_count = int(document.page_count)
            if page_count == 0:
                raise InvalidDocumentError()
            if page_count > self._max_pages:
                raise OcrPageLimitError()

            metadata_signals = await asyncio.to_thread(
                self._visuals.analyze_pdf_metadata,
                data,
            )
            blocks: list[TextBlock] = []
            signals: list[VisualSignal] = list(metadata_signals)
            used_ocr = False
            language: str | None = None

            for index in range(page_count):
                page = await asyncio.to_thread(document.load_page, index)
                page_number = index + 1
                native_blocks = await asyncio.to_thread(
                    self._native_blocks,
                    page,
                    page_number,
                )
                pixmap = await asyncio.to_thread(
                    page.get_pixmap,
                    dpi=self._render_dpi,
                )
                if int(pixmap.width) * int(pixmap.height) > self._max_image_pixels:
                    raise OcrImageTooLargeError()
                png = await asyncio.to_thread(pixmap.tobytes, "png")

                signals.extend(
                    await asyncio.to_thread(
                        self._visuals.analyze_image,
                        png,
                        page=page_number,
                    )
                )

                native_chars = sum(len(block.text.strip()) for block in native_blocks)
                if native_chars >= self._native_min_chars:
                    blocks.extend(native_blocks)
                    continue

                ocr_result = await self._run_ocr(png)
                used_ocr = True
                language = ocr_result.language
                blocks.extend(
                    TextBlock(
                        text=block.text,
                        page=page_number,
                        bbox=block.bbox,
                        confidence=block.confidence,
                    )
                    for block in ocr_result.blocks
                )

            return IngestionResult(
                blocks=tuple(blocks),
                signals=tuple(signals),
                page_count=page_count,
                used_ocr=used_ocr,
                source_type="pdf_ocr" if used_ocr else "pdf_native",
                language=language,
            )
        finally:
            document.close()

    async def _run_ocr(self, image: bytes) -> OcrResult:
        try:
            return await asyncio.wait_for(
                self._ocr.recognize(
                    image,
                    language=self._languages[0],
                ),
                timeout=self._timeout,
            )
        except TimeoutError as exc:
            raise OcrTimeoutError() from exc

    def _ensure_image_size(self, data: bytes) -> None:
        buffer = np.frombuffer(data, dtype=np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise InvalidDocumentError()
        height, width = image.shape[:2]
        if width * height > self._max_image_pixels:
            raise OcrImageTooLargeError()

    @staticmethod
    def _native_blocks(
        page: object,
        page_number: int,
    ) -> list[TextBlock]:
        try:
            raw_blocks = page.get_text("blocks")  # type: ignore[attr-defined]
        except Exception as exc:
            raise InvalidDocumentError() from exc

        blocks: list[TextBlock] = []
        for item in raw_blocks:
            if len(item) < 7 or int(item[6]) != 0:
                continue
            text = str(item[4]).strip()
            if not text:
                continue
            bbox: BBox = (
                float(item[0]),
                float(item[1]),
                float(item[2]),
                float(item[3]),
            )
            blocks.append(
                TextBlock(
                    text=text,
                    page=page_number,
                    bbox=bbox,
                    confidence=1.0,
                )
            )
        return blocks
