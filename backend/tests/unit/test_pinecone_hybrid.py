from datetime import date
from typing import Any

import pytest

from paysentineliq.application.errors import RagUnavailableError
from paysentineliq.domain.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeFilter,
    Provenance,
)
from paysentineliq.domain.ports.retrieval import (
    DENSE_EMBEDDING_DIMENSION,
    HybridEmbeddedChunk,
    SparseVector,
)
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.rag.pinecone_hybrid import (
    PineconeHybridVectorStore,
    validate_pinecone_index,
)

pytestmark = pytest.mark.unit


class FakeIndex:
    def __init__(self, matches: list[dict[str, Any]] | None = None) -> None:
        self.matches = matches or []
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def upsert(self, *, vectors: list[dict[str, Any]], namespace: str) -> None:
        self.calls.append(("upsert", {"vectors": vectors, "namespace": namespace}))

    def query(
        self,
        *,
        vector: list[float] | None = None,
        sparse_vector: dict[str, list[int] | list[float]] | None = None,
        top_k: int,
        include_metadata: bool,
        filter: dict[str, Any] | None,
        namespace: str,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "query",
                {
                    "vector": vector,
                    "sparse_vector": sparse_vector,
                    "top_k": top_k,
                    "include_metadata": include_metadata,
                    "filter": filter,
                    "namespace": namespace,
                },
            ),
        )
        return {"matches": self.matches}

    def delete(self, *, filter: dict[str, Any], namespace: str) -> None:
        self.calls.append(("delete", {"filter": filter, "namespace": namespace}))


def _document() -> KnowledgeDocument:
    return KnowledgeDocument(
        key="faq/faq.pdf",
        category="faq",
        path="knowledge/faq/faq.pdf",
        title="FAQ",
        source="oficial",
        provenance=Provenance.OFFICIAL,
        version="1",
        valid_from=date(2024, 1, 1),
        valid_until=date(2024, 12, 31),
        content_hash="a" * 64,
        pages=(),
    )


def _chunks() -> tuple[HybridEmbeddedChunk, ...]:
    chunk = KnowledgeChunk(
        document_key="faq/faq.pdf",
        index=0,
        section="page 1",
        position=0,
        content="conteudo",
        content_hash="b" * 64,
    )
    dense = tuple(1.0 if index == 0 else 0.0 for index in range(DENSE_EMBEDDING_DIMENSION))
    return (
        HybridEmbeddedChunk(
            chunk=chunk,
            dense_embedding=dense,
            sparse_embedding=SparseVector(((10, 0.5), (20, 1.5))),
        ),
    )


async def test_hybrid_upsert_sends_dense_and_sparse_values() -> None:
    index = FakeIndex()
    store = PineconeHybridVectorStore(index, namespace="test")

    result = await store.upsert_hybrid_document(
        _document(),
        _chunks(),
        embedding_model="BAAI/bge-m3",
    )

    assert result.chunks_written == 1
    assert [call[0] for call in index.calls] == ["delete", "upsert"]
    assert index.calls[0][1]["filter"] == {"document_key": "faq/faq.pdf"}
    vector = index.calls[1][1]["vectors"][0]
    assert len(vector["values"]) == 1024
    assert vector["sparse_values"] == {
        "indices": [10, 20],
        "values": [0.5, 1.5],
    }
    assert vector["metadata"]["retrieval_mode"] == "hybrid"


async def test_hybrid_dense_and_sparse_queries_use_native_vectors() -> None:
    index = FakeIndex(
        [
            {
                "id": "faq/faq.pdf:0:" + "b" * 64,
                "score": 0.8,
                "metadata": {
                    "document_key": "faq/faq.pdf",
                    "path": "knowledge/faq/faq.pdf",
                    "category": "faq",
                    "title": "FAQ",
                    "source": "oficial",
                    "provenance": "official",
                    "version": "1",
                    "valid_from": "2024-01-01",
                    "valid_until": "2024-12-31",
                    "section": "page 1",
                    "chunk_index": 0,
                    "content": "conteudo",
                    "content_hash": "b" * 64,
                },
            },
        ],
    )
    store = PineconeHybridVectorStore(index, namespace="test")
    dense = tuple(1.0 if position == 0 else 0.0 for position in range(1024))

    dense_result = await store.dense_query(
        dense,
        limit=5,
        filters=KnowledgeFilter(categories=("faq",)),
    )
    sparse_result = await store.sparse_query(
        SparseVector(((10, 1.0),)),
        limit=3,
        filters=KnowledgeFilter(),
    )

    assert len(dense_result) == 1
    assert len(sparse_result) == 1
    dense_payload = index.calls[0][1]
    sparse_payload = index.calls[1][1]
    assert len(dense_payload["vector"]) == 1024
    assert dense_payload["top_k"] == 5
    assert dense_payload["filter"] == {"category": {"$in": ["faq"]}}
    assert sparse_payload["vector"] == [0.0] * 1024
    assert sparse_payload["sparse_vector"] == {"indices": [10], "values": [1.0]}
    assert sparse_payload["top_k"] == 3


async def test_hybrid_sparse_query_without_terms_is_empty() -> None:
    index = FakeIndex()
    store = PineconeHybridVectorStore(index, namespace="test")

    assert (
        await store.sparse_query(
            SparseVector(()),
            limit=5,
            filters=KnowledgeFilter(),
        )
        == ()
    )
    assert index.calls == []


async def test_hybrid_store_rejects_wrong_dense_dimension() -> None:
    store = PineconeHybridVectorStore(FakeIndex(), namespace="test")

    with pytest.raises(ValueError):
        await store.dense_query((1.0, 0.0), limit=1, filters=KnowledgeFilter())


def test_validate_pinecone_index_requires_1024_and_dotproduct() -> None:
    validate_pinecone_index({"dimension": 1024, "metric": "dotproduct"})

    with pytest.raises(RagUnavailableError):
        validate_pinecone_index({"dimension": 1536, "metric": "dotproduct"})
    with pytest.raises(RagUnavailableError):
        validate_pinecone_index({"dimension": 1024, "metric": "cosine"})


def test_hybrid_from_settings_requires_configuration() -> None:
    settings = Settings(
        app_env="local",
        jwt_secret="s" * 64,
        security_hash_secret="h" * 32,
    )

    with pytest.raises(RagUnavailableError):
        PineconeHybridVectorStore.from_settings(settings)
