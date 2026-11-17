from typing import Protocol

from paysentineliq.domain.knowledge import (
    KnowledgeDocument,
    KnowledgeFilter,
    RetrievedChunk,
    UpsertResult,
)
from paysentineliq.domain.ports.retrieval import (
    HybridEmbeddedChunk,
    SparseVector,
)


class HybridVectorStorePort(Protocol):
    async def upsert_hybrid_document(
        self,
        document: KnowledgeDocument,
        chunks: tuple[HybridEmbeddedChunk, ...],
        *,
        embedding_model: str = "",
    ) -> UpsertResult: ...

    async def delete_document(self, document_key: str) -> None: ...

    async def dense_query(
        self,
        embedding: tuple[float, ...],
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]: ...

    async def sparse_query(
        self,
        sparse: SparseVector,
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]: ...
