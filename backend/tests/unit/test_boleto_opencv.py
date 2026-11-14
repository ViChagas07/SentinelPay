import sys
import types
from typing import Any

import numpy as np
import pytest

from paysentineliq.domain.boleto.analysis import BarcodeRead
from paysentineliq.infrastructure.barcode.opencv import OpenCvBarcodeReader
from tests.support.boleto_factory import build_boleto


class _Detector:
    def __init__(self, result: Any) -> None:
        self._result = result

    def detectAndDecode(self, image: Any) -> Any:
        return self._result


def _install_fake_cv2(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: Any = ("", None, None),
    decode_ok: bool = True,
    with_barcode: bool = True,
) -> None:
    fake: Any = types.ModuleType("cv2")
    fake.IMREAD_COLOR = 1
    fake.error = RuntimeError
    fake.imdecode = lambda buffer, flags: np.zeros((1, 1, 3), dtype=np.uint8) if decode_ok else None
    if with_barcode:
        fake.barcode = types.SimpleNamespace(BarcodeDetector=lambda: _Detector(result))
    monkeypatch.setitem(sys.modules, "cv2", fake)


async def test_reader_returns_44_digits_from_detector(monkeypatch: pytest.MonkeyPatch) -> None:
    boleto = build_boleto()
    _install_fake_cv2(monkeypatch, result=(boleto.barcode, None, None))

    result = await OpenCvBarcodeReader().read(b"image")

    assert result == BarcodeRead(status="read", digits=boleto.barcode)


async def test_reader_reports_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_cv2(monkeypatch, result=("", None, None))

    result = await OpenCvBarcodeReader().read(b"image")

    assert result.status == "not_found"
    assert result.digits is None


async def test_reader_reports_detector_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_cv2(monkeypatch, with_barcode=False)

    result = await OpenCvBarcodeReader().read(b"image")

    assert result.status == "not_validated"
    assert result.reason == "barcode_detector_unavailable"


async def test_reader_reports_invalid_image(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_cv2(monkeypatch, decode_ok=False)

    result = await OpenCvBarcodeReader().read(b"image")

    assert result.status == "error"
    assert result.reason == "image_decode_failed"


async def test_reader_reports_empty_image() -> None:
    result = await OpenCvBarcodeReader().read(b"")

    assert result.status == "error"
    assert result.reason == "empty_image"


async def test_reader_reports_non_44_digit_decode(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_cv2(monkeypatch, result=("123456", None, None))

    result = await OpenCvBarcodeReader().read(b"image")

    assert result.status == "not_validated"
    assert result.reason == "barcode_not_44_digits"
