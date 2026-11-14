from datetime import date

import pytest

from paysentineliq.application.errors import RagUnavailableError
from paysentineliq.application.queries.knowledge_retrieval import (
    KnowledgeQuery,
    KnowledgeRetriever,
)
from paysentineliq.domain.knowledge import (
    EmbeddedChunk,
    KnowledgeDocument,
    KnowledgeFilter,
    Provenance,
    RetrievedChunk,
    UpsertResult,
)

pytestmark = pytest.mark.unit


class FakeEmbedder:
    dimension = 3

    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self._fail = fail

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.calls += 1
        if self._fail:
            raise RagUnavailableError("offline")
        return tuple((1.0, 0.0, 0.0) for _ in texts)


class FakeStore:
    def __init__(
        self,
        rows: tuple[RetrievedChunk, ...] = (),
        *,
        fail: bool = False,
    ) -> None:
        self.rows = rows
        self.fail = fail
        self.calls: list[tuple[tuple[float, ...], int, KnowledgeFilter]] = []

    async def upsert_document(
        self,
        document: KnowledgeDocument,
        chunks: tuple[EmbeddedChunk, ...],
    ) -> UpsertResult:
        raise AssertionError("not used")

    async def delete_document(self, document_key: str) -> None:
        raise AssertionError("not used")

    async def query(
        self,
        embedding: tuple[float, ...],
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]:
        self.calls.append((embedding, limit, filters))
        if self.fail:
            raise RagUnavailableError("offline")
        return self.rows


def _row(*, provenance: Provenance = Provenance.OFFICIAL) -> RetrievedChunk:
    return RetrievedChunk(
        document_key="febraban/manual.pdf",
        path="knowledge/febraban/manual.pdf",
        category="febraban",
        title="Manual FEBRABAN",
        source="https://www.bcb.gov.br/norma",
        provenance=provenance,
        version="1",
        valid_from=date(2024, 1, 1),
        valid_until=date(2024, 12, 31),
        section="page 1",
        content="Trecho relevante.",
        content_hash="b" * 64,
        chunk_index=0,
        score=0.9,
    )


async def test_retriever_returns_passages_with_citations_and_filters() -> None:
    embedder = FakeEmbedder()
    store = FakeStore((_row(),))
    retriever = KnowledgeRetriever(embedder, store)

    result = await retriever.retrieve(
        KnowledgeQuery(
            text="linha digitavel",
            categories=("febraban",),
            as_of=date(2024, 6, 1),
            limit=3,
        ),
    )

    assert result.rag_unavailable is False
    assert len(result.passages) == 1
    passage = result.passages[0]
    assert passage.citation.authoritative is True
    assert passage.citation.document_key == "febraban/manual.pdf"
    assert passage.citation.section == "page 1"
    assert passage.citation.provenance is Provenance.OFFICIAL
    assert store.calls[0][1] == 3
    assert store.calls[0][2].categories == ("febraban",)
    assert store.calls[0][2].as_of == date(2024, 6, 1)


async def test_compiled_citation_is_labeled_non_authoritative() -> None:
    retriever = KnowledgeRetriever(
        FakeEmbedder(),
        FakeStore((_row(provenance=Provenance.COMPILED),)),
    )

    result = await retriever.retrieve(KnowledgeQuery(text="consulta"))

    assert result.passages[0].citation.authoritative is False
    assert result.passages[0].citation.provenance is Provenance.COMPILED


async def test_retriever_degrades_when_store_fails() -> None:
    retriever = KnowledgeRetriever(FakeEmbedder(), FakeStore(fail=True))

    result = await retriever.retrieve(KnowledgeQuery(text="consulta"))

    assert result.passages == ()
    assert result.rag_unavailable is True
    assert result.reason == "rag_unavailable"


async def test_retriever_degrades_when_embedder_fails() -> None:
    retriever = KnowledgeRetriever(FakeEmbedder(fail=True), FakeStore())

    result = await retriever.retrieve(KnowledgeQuery(text="consulta"))

    assert result.passages == ()
    assert result.rag_unavailable is True
