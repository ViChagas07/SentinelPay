from typing import Protocol

from paysentineliq.domain.ingestion import IngestionResult


class DocumentIngestionPort(Protocol):
    async def ingest(self, data: bytes) -> IngestionResult: ...
