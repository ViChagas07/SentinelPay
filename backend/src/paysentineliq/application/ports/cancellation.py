from typing import Protocol
from uuid import UUID


class CancellationPort(Protocol):
    async def request(self, analysis_id: UUID) -> None: ...

    async def clear(self, analysis_id: UUID) -> None: ...

    async def is_cancelled(self, analysis_id: UUID) -> bool: ...


class NullCancellation:
    async def request(self, analysis_id: UUID) -> None:
        return None

    async def clear(self, analysis_id: UUID) -> None:
        return None

    async def is_cancelled(self, analysis_id: UUID) -> bool:
        return False
