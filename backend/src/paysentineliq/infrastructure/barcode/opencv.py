import asyncio
from typing import Any

import numpy as np

from paysentineliq.domain.boleto.analysis import BarcodeRead
from paysentineliq.domain.boleto.digits import only_digits


class OpenCvBarcodeReader:
    async def read(self, image: bytes) -> BarcodeRead:
        return await asyncio.to_thread(self._read_sync, image)

    def _read_sync(self, image: bytes) -> BarcodeRead:
        if not image:
            return BarcodeRead(status="error", reason="empty_image")
        try:
            import cv2
        except ImportError:
            return BarcodeRead(status="not_validated", reason="opencv_unavailable")

        buffer = np.frombuffer(image, dtype=np.uint8)
        decoded: Any = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if decoded is None:
            return BarcodeRead(status="error", reason="image_decode_failed")

        try:
            detector = cv2.barcode.BarcodeDetector()
            result = detector.detectAndDecode(decoded)
        except (AttributeError, cv2.error):
            return BarcodeRead(status="not_validated", reason="barcode_detector_unavailable")

        text = _first_decoded_text(result)
        if text is None:
            return BarcodeRead(status="not_found", reason="barcode_not_found")
        digits = only_digits(text)
        if len(digits) != 44:
            return BarcodeRead(status="not_validated", reason="barcode_not_44_digits")
        return BarcodeRead(status="read", digits=digits)


def _first_decoded_text(value: Any) -> str | None:
    for text in _strings(value):
        cleaned = text.strip()
        if cleaned:
            return cleaned
    return None


def _strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        result: list[str] = []
        for item in value:
            result.extend(_strings(item))
        return tuple(result)
    if hasattr(value, "tolist"):
        return _strings(value.tolist())
    return ()
