from paysentineliq.application.ports.barcode import BarcodeReaderPort
from paysentineliq.application.use_cases.boleto_analysis import BoletoAnalysisService
from paysentineliq.domain.boleto.analysis import BarcodeRead
from tests.support.boleto_factory import build_boleto


class FakeBarcodeReader:
    def __init__(self, result: BarcodeRead | Exception) -> None:
        self.result = result
        self.calls = 0

    async def read(self, image: bytes) -> BarcodeRead:
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _service(reader: BarcodeReaderPort | None) -> BoletoAnalysisService:
    return BoletoAnalysisService(barcode_reader=reader)


async def test_service_uses_barcode_reader_when_image_is_provided() -> None:
    boleto = build_boleto()
    reader = FakeBarcodeReader(BarcodeRead(status="read", digits=boleto.barcode))
    service = _service(reader)

    analysis = await service.analyze(boleto.ocr_text(), barcode_image=b"image")

    assert reader.calls == 1
    assert analysis.barcode_read.status == "read"
    assert analysis.subscore == 0
    assert analysis.decoded is not None


async def test_service_skips_reader_without_image() -> None:
    boleto = build_boleto()
    reader = FakeBarcodeReader(BarcodeRead(status="read", digits=boleto.barcode))
    service = _service(reader)

    analysis = await service.analyze(boleto.ocr_text())

    assert reader.calls == 0
    assert analysis.barcode_read.status == "not_validated"
    assert analysis.barcode_read.reason == "image_not_provided"
    assert analysis.subscore == 0


async def test_service_handles_missing_reader() -> None:
    boleto = build_boleto()
    service = _service(None)

    analysis = await service.analyze(boleto.ocr_text(), barcode_image=b"image")

    assert analysis.barcode_read.status == "not_validated"
    assert analysis.barcode_read.reason == "reader_unavailable"
    assert analysis.subscore == 0


async def test_service_degrades_when_reader_fails() -> None:
    boleto = build_boleto()
    reader = FakeBarcodeReader(RuntimeError("boom"))
    service = _service(reader)

    analysis = await service.analyze(boleto.ocr_text(), barcode_image=b"image")

    assert analysis.barcode_read.status == "error"
    assert analysis.barcode_read.reason == "reader_failed"
    assert [evidence.rule_id for evidence in analysis.evidence] == ["barcode_unreadable"]
    assert analysis.subscore == 10
