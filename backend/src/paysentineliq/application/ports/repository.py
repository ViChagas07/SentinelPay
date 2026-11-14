from typing import Protocol
from uuid import UUID


class ExampleRepository(Protocol):
    async def exists(self, item_id: UUID) -> bool: ...
