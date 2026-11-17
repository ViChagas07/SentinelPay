import asyncio
from datetime import date
from typing import Any, Protocol

from paysentineliq.application.errors import RagUnavailableError
from paysentineliq.domain.knowledge import (
    KnowledgeDocument,
    KnowledgeFilter,
    Provenance,
    RetrievedChunk,
    UpsertResult,
)
from paysentineliq.domain.ports.retrieval import (
    DENSE_EMBEDDING_DIMENSION,
    HybridEmbeddedChunk,
    SparseVector,
)
from paysentineliq.infrastructure.config import Settings


class PineconeHybridIndexPort(Protocol):
    def upsert(
        self,
        *,
        vectors: list[dict[str, Any]],
        namespace: str,
    ) -> Any: ...

    def query(
        self,
        *,
        vector: list[float] | None = None,
        sparse_vector: dict[str, list[int] | list[float]] | None = None,
        top_k: int,
        include_metadata: bool,
        filter: dict[str, Any] | None,
        namespace: str,
    ) -> Any: ...

    def delete(
        self,
        *,
        filter: dict[str, Any],
        namespace: str,
    ) -> None: ...


def _date_or_default(value: date | None, default: str) -> str:
    return value.isoformat() if value is not None else default


def _parse_date(value: object, default: str) -> date | None:
    if not isinstance(value, str) or value == default:
        return None
    return date.fromisoformat(value)


def _field(value: object, name: str) -> object:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def validate_pinecone_index(description: object) -> None:
    dimension = _field(description, "dimension")
    metric = _field(description, "metric")
    if dimension != DENSE_EMBEDDING_DIMENSION:
        raise RagUnavailableError(
            "Pinecone index must have dimension 1024 for hybrid retrieval",
        )
    if metric != "dotproduct":
        raise RagUnavailableError(
            "Pinecone index must use the dotproduct metric for hybrid retrieval",
        )


class PineconeHybridVectorStore:
    def __init__(
        self,
        index: PineconeHybridIndexPort,
        *,
        namespace: str = "knowledge-hybrid",
        dimension: int = DENSE_EMBEDDING_DIMENSION,
    ) -> None:
        if dimension != DENSE_EMBEDDING_DIMENSION:
            raise ValueError("hybrid retrieval requires 1024 dimensions")
        if not namespace.strip():
            raise ValueError("namespace is required")
        self._index = index
        self._namespace = namespace
        self._dimension = dimension

    @classmethod
    def from_settings(cls, settings: Settings) -> "PineconeHybridVectorStore":
        if not settings.pinecone_api_key or not settings.pinecone_index:
            raise RagUnavailableError("Pinecone is not configured")
        from pinecone import Pinecone

        client = Pinecone(api_key=settings.pinecone_api_key)
        description = client.describe_index(name=settings.pinecone_index)
        validate_pinecone_index(description)
        index = client.index(name=settings.pinecone_index)
        return cls(
            index,
            namespace=f"{settings.pinecone_namespace}-hybrid",
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    def _validate(self, embedding: tuple[float, ...]) -> None:
        if len(embedding) != self._dimension:
            raise ValueError("dense embedding dimension must be 1024")

    def _metadata(
        self,
        document: KnowledgeDocument,
        item: HybridEmbeddedChunk,
    ) -> dict[str, Any]:
        chunk = item.chunk
        return {
            "document_key": document.key,
            "path": document.path,
            "category": document.category,
            "title": document.title,
            "source": document.source,
            "provenance": document.provenance.value,
            "version": document.version or "",
            "valid_from": _date_or_default(document.valid_from, "0001-01-01"),
            "valid_until": _date_or_default(document.valid_until, "9999-12-31"),
            "section": chunk.section,
            "chunk_index": chunk.index,
            "content": chunk.content,
            "content_hash": chunk.content_hash,
            "retrieval_mode": "hybrid",
        }

    async def upsert_hybrid_document(
        self,
        document: KnowledgeDocument,
        chunks: tuple[HybridEmbeddedChunk, ...],
        *,
        embedding_model: str = "",
    ) -> UpsertResult:
        if not chunks:
            raise ValueError("document must have at least one chunk")
        vectors: list[dict[str, Any]] = []
        for item in chunks:
            self._validate(item.dense_embedding)
            if item.chunk.document_key != document.key:
                raise ValueError("chunk document_key does not match document")
            metadata = self._metadata(document, item)
            metadata["embedding_model"] = embedding_model
            vector: dict[str, Any] = {
                "id": f"{document.key}:{item.chunk.index}:{item.chunk.content_hash}",
                "values": list(item.dense_embedding),
                "metadata": metadata,
            }
            if item.sparse_embedding.weights:
                vector["sparse_values"] = {
                    "indices": [token_id for token_id, _ in item.sparse_embedding.weights],
                    "values": [weight for _, weight in item.sparse_embedding.weights],
                }
            vectors.append(vector)
        await asyncio.to_thread(
            self._index.delete,
            filter={"document_key": document.key},
            namespace=self._namespace,
        )
        await asyncio.to_thread(
            self._index.upsert,
            vectors=vectors,
            namespace=self._namespace,
        )
        return UpsertResult(
            document_key=document.key,
            skipped=False,
            chunks_written=len(chunks),
            chunks_deleted=0,
        )

    async def delete_document(self, document_key: str) -> None:
        await asyncio.to_thread(
            self._index.delete,
            filter={"document_key": document_key},
            namespace=self._namespace,
        )

    async def dense_query(
        self,
        embedding: tuple[float, ...],
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]:
        self._validate(embedding)
        if limit <= 0:
            raise ValueError("limit must be positive")
        response = await asyncio.to_thread(
            self._index.query,
            vector=list(embedding),
            top_k=limit,
            include_metadata=True,
            filter=_pinecone_filter(filters),
            namespace=self._namespace,
        )
        return _parse_matches(response)

    async def sparse_query(
        self,
        sparse: SparseVector,
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if not sparse.weights:
            return ()
        response = await asyncio.to_thread(
            self._index.query,
            vector=[0.0] * DENSE_EMBEDDING_DIMENSION,
            sparse_vector={
                "indices": [token_id for token_id, _ in sparse.weights],
                "values": [weight for _, weight in sparse.weights],
            },
            top_k=limit,
            include_metadata=True,
            filter=_pinecone_filter(filters),
            namespace=self._namespace,
        )
        return _parse_matches(response)


def _pinecone_filter(filters: KnowledgeFilter) -> dict[str, Any] | None:
    pinecone_filter: dict[str, Any] = {}
    if filters.categories:
        pinecone_filter["category"] = {"$in": list(filters.categories)}
    if filters.provenance:
        pinecone_filter["provenance"] = {
            "$in": [provenance.value for provenance in filters.provenance],
        }
    if filters.as_of is not None:
        pinecone_filter["valid_from"] = {"$lte": filters.as_of.isoformat()}
        pinecone_filter["valid_until"] = {"$gte": filters.as_of.isoformat()}
    return pinecone_filter or None


def _parse_matches(response: object) -> tuple[RetrievedChunk, ...]:
    matches = (
        response.get("matches", [])
        if isinstance(response, dict)
        else getattr(response, "matches", [])
    )
    retrieved: list[RetrievedChunk] = []
    for match in matches:
        if isinstance(match, dict):
            metadata = match.get("metadata", {})
            score = match.get("score", 0.0)
        else:
            metadata = getattr(match, "metadata", {})
            score = getattr(match, "score", 0.0)
        if not isinstance(metadata, dict):
            continue
        retrieved.append(
            RetrievedChunk(
                document_key=str(metadata.get("document_key", "")),
                path=str(metadata.get("path", "")),
                category=str(metadata.get("category", "")),
                title=str(metadata.get("title", "")),
                source=str(metadata.get("source", "unknown")),
                provenance=Provenance(str(metadata.get("provenance", "unknown"))),
                version=str(metadata.get("version") or "") or None,
                valid_from=_parse_date(metadata.get("valid_from"), "0001-01-01"),
                valid_until=_parse_date(metadata.get("valid_until"), "9999-12-31"),
                section=str(metadata.get("section", "")),
                content=str(metadata.get("content", "")),
                content_hash=str(metadata.get("content_hash", "")),
                chunk_index=int(metadata.get("chunk_index", 0)),
                score=float(score),
            ),
        )
    return tuple(retrieved)
