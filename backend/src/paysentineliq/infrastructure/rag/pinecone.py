import asyncio
from datetime import date
from typing import Any, Protocol

from paysentineliq.application.errors import RagUnavailableError
from paysentineliq.domain.knowledge import (
    EmbeddedChunk,
    KnowledgeDocument,
    KnowledgeFilter,
    Provenance,
    RetrievedChunk,
    UpsertResult,
)
from paysentineliq.infrastructure.config import Settings


class PineconeIndexPort(Protocol):
    def upsert(
        self,
        *,
        vectors: list[dict[str, Any]],
        namespace: str,
    ) -> Any: ...

    def query(
        self,
        *,
        vector: list[float],
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


class PineconeVectorStore:
    def __init__(
        self,
        index: PineconeIndexPort,
        *,
        namespace: str = "knowledge",
        dimension: int,
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        if not namespace.strip():
            raise ValueError("namespace is required")
        self._index = index
        self._namespace = namespace
        self._dimension = dimension

    @classmethod
    def from_settings(cls, settings: Settings) -> "PineconeVectorStore":
        if not settings.pinecone_api_key or not settings.pinecone_index:
            raise RagUnavailableError("Pinecone is not configured")
        if settings.embedding_dim <= 0:
            raise RagUnavailableError("EMBEDDING_DIM is required")
        from pinecone import Pinecone

        client = Pinecone(api_key=settings.pinecone_api_key)
        index = client.index(name=settings.pinecone_index)
        return cls(
            index,
            namespace=settings.pinecone_namespace,
            dimension=settings.embedding_dim,
        )

    def _validate(self, embedding: tuple[float, ...]) -> None:
        if len(embedding) != self._dimension:
            raise ValueError("embedding dimension does not match the index")

    def _metadata(
        self,
        document: KnowledgeDocument,
        embedded: EmbeddedChunk,
    ) -> dict[str, Any]:
        chunk = embedded.chunk
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
        }

    async def upsert_document(
        self,
        document: KnowledgeDocument,
        chunks: tuple[EmbeddedChunk, ...],
    ) -> UpsertResult:
        if not chunks:
            raise ValueError("document must have at least one chunk")
        for embedded in chunks:
            self._validate(embedded.embedding)
            if embedded.chunk.document_key != document.key:
                raise ValueError("chunk document_key does not match document")
        vectors = [
            {
                "id": f"{document.key}:{embedded.chunk.index}:{embedded.chunk.content_hash}",
                "values": list(embedded.embedding),
                "metadata": self._metadata(document, embedded),
            }
            for embedded in chunks
        ]
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

    async def query(
        self,
        embedding: tuple[float, ...],
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]:
        self._validate(embedding)
        if limit <= 0:
            raise ValueError("limit must be positive")
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

        response = await asyncio.to_thread(
            self._index.query,
            vector=list(embedding),
            top_k=limit,
            include_metadata=True,
            filter=pinecone_filter or None,
            namespace=self._namespace,
        )
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
                    provenance=Provenance(
                        str(metadata.get("provenance", "unknown")),
                    ),
                    version=str(metadata.get("version") or "") or None,
                    valid_from=_parse_date(metadata.get("valid_from"), "0001-01-01"),
                    valid_until=_parse_date(
                        metadata.get("valid_until"),
                        "9999-12-31",
                    ),
                    section=str(metadata.get("section", "")),
                    content=str(metadata.get("content", "")),
                    content_hash=str(metadata.get("content_hash", "")),
                    chunk_index=int(metadata.get("chunk_index", 0)),
                    score=float(score),
                ),
            )
        return tuple(retrieved)
