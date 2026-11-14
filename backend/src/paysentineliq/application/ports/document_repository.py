from typing import Protocol
from uuid import UUID

from paysentineliq.domain.document import Document


class DocumentRepository(Protocol):
    async def add(self, document: Document) -> Document: ...

    async def get_by_id_for_owner(
        self,
        document_id: UUID,
        owner_id: UUID,
    ) -> Document | None: ...
