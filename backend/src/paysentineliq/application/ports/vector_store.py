from typing import Protocol

from paysentineliq.domain.knowledge import (
    EmbeddedChunk,
    KnowledgeDocument,
    KnowledgeFilter,
    RetrievedChunk,
    UpsertResult,
)


class VectorStorePort(Protocol):
    async def upsert_document(
        self,
        document: KnowledgeDocument,
        chunks: tuple[EmbeddedChunk, ...],
    ) -> UpsertResult: ...

    async def delete_document(self, document_key: str) -> None: ...

    async def query(
        self,
        embedding: tuple[float, ...],
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]: ...
