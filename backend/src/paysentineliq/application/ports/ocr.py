from dataclasses import dataclass
from typing import Protocol

from paysentineliq.domain.ingestion import BBox


@dataclass(frozen=True, slots=True)
class OcrBlock:
    text: str
    bbox: BBox | None
    confidence: float


@dataclass(frozen=True, slots=True)
class OcrResult:
    blocks: tuple[OcrBlock, ...]
    language: str
    engine: str = "paddleocr"


class OcrPort(Protocol):
    async def recognize(
        self,
        image: bytes,
        *,
        language: str | None = None,
    ) -> OcrResult: ...
