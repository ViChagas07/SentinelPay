from typing import Protocol

from paysentineliq.domain.document import Document


class DocumentWriteRepository(Protocol):
    async def add(self, document: Document) -> Document: ...
