from typing import Protocol

from paysentineliq.domain.boleto.analysis import BarcodeRead


class BarcodeReaderPort(Protocol):
    async def read(self, image: bytes) -> BarcodeRead: ...
