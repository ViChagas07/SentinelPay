from datetime import date
from typing import Any

import pytest

from paysentineliq.application.errors import RagUnavailableError
from paysentineliq.domain.knowledge import (
    EmbeddedChunk,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeFilter,
    Provenance,
)
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.rag.pinecone import PineconeVectorStore

pytestmark = pytest.mark.unit


class FakeIndex:
    def __init__(self, matches: list[dict[str, Any]] | None = None) -> None:
        self.matches = matches or []
        self.calls: list[tuple[str, Any]] = []

    def upsert(self, *, vectors: list[dict[str, Any]], namespace: str) -> None:
        self.calls.append(("upsert", {"vectors": vectors, "namespace": namespace}))

    def query(
        self,
        *,
        vector: list[float],
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
        source="blog.example.com",
        provenance=Provenance.COMPILED,
        version="1",
        valid_from=date(2024, 1, 1),
        valid_until=date(2024, 12, 31),
        content_hash="a" * 64,
        pages=(),
    )


def _chunks() -> tuple[EmbeddedChunk, ...]:
    chunk = KnowledgeChunk(
        document_key="faq/faq.pdf",
        index=0,
        section="page 1",
        position=0,
        content="conteudo",
        content_hash="b" * 64,
    )
    return (EmbeddedChunk(chunk=chunk, embedding=(1.0, 0.0, 0.0)),)


async def test_upsert_deletes_old_vectors_then_upserts_metadata() -> None:
    index = FakeIndex()
    store = PineconeVectorStore(index, namespace="test", dimension=3)

    result = await store.upsert_document(_document(), _chunks())

    assert result.skipped is False
    assert result.chunks_written == 1
    assert [call[0] for call in index.calls] == ["delete", "upsert"]
    delete_payload = index.calls[0][1]
    assert delete_payload["filter"] == {"document_key": "faq/faq.pdf"}
    upsert_payload = index.calls[1][1]
    vector = upsert_payload["vectors"][0]
    assert vector["id"].startswith("faq/faq.pdf:0:")
    assert vector["values"] == [1.0, 0.0, 0.0]
    assert vector["metadata"]["provenance"] == "compiled"
    assert vector["metadata"]["content"] == "conteudo"
    assert vector["metadata"]["valid_from"] == "2024-01-01"
    assert vector["metadata"]["valid_until"] == "2024-12-31"
    assert upsert_payload["namespace"] == "test"


async def test_query_returns_citations_and_metadata_filter() -> None:
    index = FakeIndex(
        [
            {
                "id": "faq/faq.pdf:0:" + "b" * 64,
                "score": 0.9,
                "metadata": {
                    "document_key": "faq/faq.pdf",
                    "path": "knowledge/faq/faq.pdf",
                    "category": "faq",
                    "title": "FAQ",
                    "source": "blog.example.com",
                    "provenance": "compiled",
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
    store = PineconeVectorStore(index, namespace="test", dimension=3)

    passages = await store.query(
        (1.0, 0.0, 0.0),
        limit=5,
        filters=KnowledgeFilter(
            categories=("faq",),
            provenance=(Provenance.COMPILED,),
            as_of=date(2024, 6, 1),
        ),
    )

    assert len(passages) == 1
    assert passages[0].authoritative is False
    assert passages[0].provenance is Provenance.COMPILED
    assert passages[0].section == "page 1"
    payload = index.calls[0][1]
    assert payload["top_k"] == 5
    assert payload["include_metadata"] is True
    assert payload["filter"] == {
        "category": {"$in": ["faq"]},
        "provenance": {"$in": ["compiled"]},
        "valid_from": {"$lte": "2024-06-01"},
        "valid_until": {"$gte": "2024-06-01"},
    }


async def test_delete_by_document_and_dimension_validation() -> None:
    index = FakeIndex()
    store = PineconeVectorStore(index, namespace="test", dimension=3)

    await store.delete_document("faq/faq.pdf")

    assert index.calls[0][1]["filter"] == {"document_key": "faq/faq.pdf"}

    with pytest.raises(ValueError):
        await store.query((1.0, 0.0), limit=1, filters=KnowledgeFilter())


def test_from_settings_requires_pinecone_configuration() -> None:
    settings = Settings(app_env="local", jwt_secret="s" * 64, security_hash_secret="h" * 32)

    with pytest.raises(RagUnavailableError):
        PineconeVectorStore.from_settings(settings)
