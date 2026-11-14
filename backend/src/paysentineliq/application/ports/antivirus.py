from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True, slots=True)
class ScanResult:
    clean: bool
    reason: str | None


class AntivirusScanner(Protocol):
    async def scan(
        self,
        stream: BinaryIO,
        *,
        content_type: str,
    ) -> ScanResult: ...
