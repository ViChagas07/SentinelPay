from dataclasses import dataclass
from typing import Literal

BBox = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class TextBlock:
    text: str
    page: int
    bbox: BBox | None
    confidence: float


@dataclass(frozen=True, slots=True)
class VisualSignal:
    name: str
    value: float
    explanation: str
    page: int | None = None
    region: BBox | None = None


@dataclass(frozen=True, slots=True)
class IngestionResult:
    blocks: tuple[TextBlock, ...]
    signals: tuple[VisualSignal, ...]
    page_count: int
    used_ocr: bool
    source_type: Literal["pdf_native", "pdf_ocr", "image"]
    language: str | None
