import logging

from paysentineliq.application.ports.barcode import BarcodeReaderPort
from paysentineliq.domain.boleto.analysis import BarcodeRead, BoletoAnalysis, analyze_boleto
from paysentineliq.domain.boleto.bank_directory import BankDirectory, load_bank_directory
from paysentineliq.domain.boleto.extraction import extract_boleto_fields

_logger = logging.getLogger("paysentineliq")


class BoletoAnalysisService:
    def __init__(
        self,
        *,
        barcode_reader: BarcodeReaderPort | None = None,
        bank_directory: BankDirectory | None = None,
    ) -> None:
        self._barcode_reader = barcode_reader
        self._bank_directory = (
            bank_directory if bank_directory is not None else load_bank_directory()
        )

    async def analyze(
        self,
        text: str,
        *,
        barcode_image: bytes | None = None,
    ) -> BoletoAnalysis:
        if barcode_image is None:
            barcode_read = BarcodeRead(status="not_validated", reason="image_not_provided")
        elif self._barcode_reader is None:
            barcode_read = BarcodeRead(status="not_validated", reason="reader_unavailable")
        else:
            try:
                barcode_read = await self._barcode_reader.read(barcode_image)
            except Exception:
                _logger.error("boleto_barcode_read_failed")
                barcode_read = BarcodeRead(status="error", reason="reader_failed")

        fields = extract_boleto_fields(text, bank_directory=self._bank_directory)
        return analyze_boleto(
            fields,
            barcode_read=barcode_read,
            bank_directory=self._bank_directory,
        )
