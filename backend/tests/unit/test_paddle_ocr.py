import io
from typing import Any

import numpy as np
import pytest
from PIL import Image

from paysentineliq.application.errors import (
    InvalidDocumentError,
    OcrUnavailableError,
)
from paysentineliq.infrastructure.ocr.paddle import PaddleOcrAdapter

pytestmark = pytest.mark.unit


class FakeEngine:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self._results = results
        self.calls = 0

    def predict(self, image: Any) -> list[dict[str, Any]]:
        self.calls += 1
        return self._results


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _adapter(
    results: list[dict[str, Any]],
    *,
    languages: tuple[str, ...] = ("pt", "es", "en"),
) -> tuple[PaddleOcrAdapter, FakeEngine, list[str]]:
    engine = FakeEngine(results)
    calls: list[str] = []

    def factory(model_language: str) -> FakeEngine:
        calls.append(model_language)
        return engine

    return (
        PaddleOcrAdapter(languages=languages, engine_factory=factory),
        engine,
        calls,
    )


async def test_recognize_parses_blocks_and_language() -> None:
    adapter, engine, calls = _adapter(
        [
            {
                "rec_texts": ["Hello", "", "world"],
                "rec_scores": np.array([0.9, 0.1, 1.2]),
                "rec_boxes": np.array(
                    [
                        [10, 20, 30, 40],
                        [1, 2, 3, 4],
                        [50, 60, 70, 80],
                    ]
                ),
            }
        ]
    )

    result = await adapter.recognize(_png_bytes())

    assert result.language == "pt"
    assert [block.text for block in result.blocks] == ["Hello", "world"]
    assert result.blocks[0].bbox == (10.0, 20.0, 30.0, 40.0)
    assert result.blocks[0].confidence == pytest.approx(0.9)
    assert result.blocks[1].confidence == 1.0
    assert engine.calls == 1
    assert calls == ["latin"]


async def test_polygon_bbox_is_supported() -> None:
    adapter, _, _ = _adapter(
        [
            {
                "rec_texts": ["text"],
                "rec_scores": [0.8],
                "rec_polys": [
                    [[5, 6], [25, 6], [25, 16], [5, 16]],
                ],
            }
        ]
    )

    result = await adapter.recognize(_png_bytes())

    assert result.blocks[0].bbox == (5.0, 6.0, 25.0, 16.0)


async def test_engine_is_loaded_once_per_model_language() -> None:
    adapter, _, calls = _adapter([])

    await adapter.recognize(_png_bytes(), language="pt")
    await adapter.recognize(_png_bytes(), language="es")
    await adapter.recognize(_png_bytes(), language="en")

    assert calls == ["latin", "en"]


async def test_unenabled_language_is_rejected() -> None:
    adapter, _, _ = _adapter([], languages=("pt",))

    with pytest.raises(ValueError):
        await adapter.recognize(_png_bytes(), language="en")


def test_invalid_languages_are_rejected() -> None:
    with pytest.raises(ValueError):
        PaddleOcrAdapter(languages=("de",))
    with pytest.raises(ValueError):
        PaddleOcrAdapter(languages=())


async def test_invalid_image_is_rejected_before_engine_load() -> None:
    adapter, _, calls = _adapter([])

    with pytest.raises(InvalidDocumentError):
        await adapter.recognize(b"not an image")

    assert calls == []


async def test_engine_failure_is_controlled() -> None:
    def factory(model_language: str) -> Any:
        raise RuntimeError("model missing")

    adapter = PaddleOcrAdapter(languages=("pt",), engine_factory=factory)

    with pytest.raises(OcrUnavailableError):
        await adapter.recognize(_png_bytes())
