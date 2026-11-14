import asyncio
import logging
import threading
from collections.abc import Callable
from typing import Any

import cv2
import numpy as np

from paysentineliq.application.errors import (
    InvalidDocumentError,
    OcrUnavailableError,
)
from paysentineliq.application.ports.ocr import OcrBlock, OcrResult
from paysentineliq.domain.ingestion import BBox

_logger = logging.getLogger("paysentineliq")

_SUPPORTED_LANGUAGES = frozenset({"pt", "es", "en"})


class PaddleOcrAdapter:
    def __init__(
        self,
        *,
        languages: tuple[str, ...],
        engine_factory: Callable[[str], Any] | None = None,
    ) -> None:
        if not languages:
            raise ValueError("at least one OCR language is required")
        invalid = set(languages) - _SUPPORTED_LANGUAGES
        if invalid:
            raise ValueError(f"unsupported OCR languages: {sorted(invalid)}")

        self._languages = languages
        self._primary_language = languages[0]
        self._engine_factory = engine_factory or _create_paddle_engine
        self._engines: dict[str, Any] = {}
        self._lock = threading.Lock()

    @property
    def primary_language(self) -> str:
        return self._primary_language

    @property
    def languages(self) -> tuple[str, ...]:
        return self._languages

    async def recognize(
        self,
        image: bytes,
        *,
        language: str | None = None,
    ) -> OcrResult:
        selected = language or self._primary_language
        if selected not in self._languages:
            raise ValueError("language is not enabled")
        return await asyncio.to_thread(
            self._recognize_sync,
            image,
            selected,
        )

    def _recognize_sync(self, image: bytes, language: str) -> OcrResult:
        if not image:
            raise InvalidDocumentError()

        buffer = np.frombuffer(image, dtype=np.uint8)
        decoded = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if decoded is None:
            raise InvalidDocumentError()

        engine = self._get_engine(language)
        try:
            with self._lock:
                results = list(engine.predict(decoded))
        except Exception as exc:
            _logger.error("ocr_inference_failed")
            raise OcrUnavailableError() from exc

        blocks: list[OcrBlock] = []
        for result in results:
            texts = _field(result, "rec_texts")
            if texts is None:
                texts = []
            scores = _field(result, "rec_scores")
            if scores is None:
                scores = []
            boxes = _field(result, "rec_boxes")
            if boxes is None:
                boxes = _field(result, "rec_polys")
            if boxes is None:
                boxes = []
            for text, score, box in zip(
                texts,
                scores,
                boxes,
                strict=False,
            ):
                normalized = str(text).strip()
                if not normalized:
                    continue
                blocks.append(
                    OcrBlock(
                        text=normalized,
                        bbox=_to_bbox(box),
                        confidence=_clamp(float(score)),
                    )
                )

        return OcrResult(
            blocks=tuple(blocks),
            language=language,
        )

    def _get_engine(self, language: str) -> Any:
        model_key = "en" if language == "en" else "latin"
        with self._lock:
            engine = self._engines.get(model_key)
            if engine is None:
                try:
                    engine = self._engine_factory(model_key)
                except Exception as exc:
                    _logger.error("ocr_engine_load_failed")
                    raise OcrUnavailableError() from exc
                self._engines[model_key] = engine
            return engine


def _create_paddle_engine(model_language: str) -> Any:
    from paddleocr import PaddleOCR

    return PaddleOCR(
        lang="en" if model_language == "en" else "pt",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
    )


def _field(result: Any, name: str) -> Any:
    try:
        return result[name]
    except (KeyError, TypeError):
        return getattr(result, name, None)


def _to_bbox(box: Any) -> BBox | None:
    if box is None:
        return None
    try:
        points = np.asarray(box, dtype=float)
    except (TypeError, ValueError):
        return None
    if points.size < 4:
        return None
    if points.ndim == 1:
        return (
            float(points[0]),
            float(points[1]),
            float(points[2]),
            float(points[3]),
        )
    if points.ndim == 3:
        points = points.reshape(-1, 2)
    if points.ndim == 2 and points.shape[1] == 4:
        return (
            float(points[:, 0].min()),
            float(points[:, 1].min()),
            float(points[:, 2].max()),
            float(points[:, 3].max()),
        )
    if points.ndim == 2 and points.shape[1] >= 2:
        return (
            float(points[:, 0].min()),
            float(points[:, 1].min()),
            float(points[:, 0].max()),
            float(points[:, 1].max()),
        )
    return None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
