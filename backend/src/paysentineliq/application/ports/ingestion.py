from collections.abc import Awaitable, Callable
from typing import Protocol

from paysentineliq.domain.ingestion import IngestionResult

PageProgressCallback = Callable[[int, int], Awaitable[None]]
CancelCheck = Callable[[], Awaitable[bool]]


class DocumentIngestionPort(Protocol):
    async def ingest(
        self,
        data: bytes,
        *,
        on_page: PageProgressCallback | None = None,
        check_cancelled: CancelCheck | None = None,
    ) -> IngestionResult: ...
