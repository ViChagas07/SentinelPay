from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True, slots=True)
class InspectedDocument:
    extension: str
    content_type: str
    size: int
    sha256: str
    page_count: int | None


class DocumentInspector(Protocol):
    async def inspect(
        self,
        stream: BinaryIO,
        *,
        max_bytes: int,
        max_pdf_pages: int,
    ) -> InspectedDocument: ...
