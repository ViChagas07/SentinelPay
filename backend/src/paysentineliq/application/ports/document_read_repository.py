from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DocumentDownloadLocation:
    s3_key: str


class DocumentReadRepository(Protocol):
    async def get_download_location(
        self,
        document_id: UUID,
        owner_id: UUID,
    ) -> DocumentDownloadLocation | None: ...
