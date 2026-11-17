from datetime import date

import pytest

from paysentineliq.application.queries.hybrid_retrieval import (
    HybridRetriever,
    fuse_rrf,
    fuse_weighted,
)
from paysentineliq.application.queries.knowledge_retrieval import KnowledgeQuery
from paysentineliq.application.queries.two_stage_retrieval import TwoStageRetriever
from paysentineliq.domain.knowledge import (
    KnowledgeDocument,
    KnowledgeFilter,
    Provenance,
    RetrievedChunk,
    UpsertResult,
)
from paysentineliq.domain.ports.retrieval import (
    HybridEmbeddedChunk,
    RerankResult,
    SparseVector,
)

pytestmark = pytest.mark.unit


def _chunk(
    *,
    key: str,
    content: str,
    index: int = 0,
    score: float = 0.9,
) -> RetrievedChunk:
    return RetrievedChunk(
        document_key=key,
        path=f"knowledge/{key}",
        category=key.split("/", 1)[0],
        title=f"Titulo {key}",
        source="oficial",
        provenance=Provenance.OFFICIAL,
        version="1",
        valid_from=None,
        valid_until=None,
        section="secao",
        content=content,
        content_hash="a" * 64,
        chunk_index=index,
        score=score,
    )


class FakeEmbedder:
    dimension = 3
    model_id = "fake-dense"

    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self._fail = fail

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.calls += 1
        if self._fail:
            raise RuntimeError("dense offline")
        vectors: list[tuple[float, ...]] = []
        for text in texts:
            lowered = text.lower()
            if "atraso" in lowered:
                vectors.append((1.0, 0.0, 0.0))
            elif "mora" in lowered:
                vectors.append((0.0, 1.0, 0.0))
            elif "late" in lowered:
                vectors.append((0.0, 0.0, 1.0))
            else:
                vectors.append((0.0, 0.0, 0.0))
        return tuple(vectors)


class FakeSparseEmbedder:
    model_id = "fake-sparse"

    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self._fail = fail

    async def embed_sparse(self, texts: tuple[str, ...]) -> tuple[SparseVector, ...]:
        self.calls += 1
        if self._fail:
            raise RuntimeError("sparse offline")
        vectors: list[SparseVector] = []
        for text in texts:
            lowered = text.lower()
            if "atraso" in lowered:
                vectors.append(SparseVector(((10, 1.0),)))
            elif "mora" in lowered:
                vectors.append(SparseVector(((20, 1.0),)))
            elif "late" in lowered:
                vectors.append(SparseVector(((30, 1.0),)))
            else:
                vectors.append(SparseVector(()))
        return tuple(vectors)


class FakeStore:
    def __init__(
        self,
        dense: dict[tuple[float, ...], tuple[RetrievedChunk, ...]] | None = None,
        sparse: dict[int, tuple[RetrievedChunk, ...]] | None = None,
        *,
        fail_dense: bool = False,
        fail_sparse: bool = False,
    ) -> None:
        self.dense = dense or {}
        self.sparse = sparse or {}
        self.fail_dense = fail_dense
        self.fail_sparse = fail_sparse
        self.filters: list[KnowledgeFilter] = []

    async def upsert_hybrid_document(
        self,
        document: KnowledgeDocument,
        chunks: tuple[HybridEmbeddedChunk, ...],
        *,
        embedding_model: str = "",
    ) -> UpsertResult:
        raise AssertionError("not used")

    async def delete_document(self, document_key: str) -> None:
        raise AssertionError("not used")

    async def dense_query(
        self,
        embedding: tuple[float, ...],
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]:
        self.filters.append(filters)
        if self.fail_dense:
            raise RuntimeError("dense store offline")
        return self.dense.get(embedding, ())[:limit]

    async def sparse_query(
        self,
        sparse: SparseVector,
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]:
        self.filters.append(filters)
        if self.fail_sparse:
            raise RuntimeError("sparse store offline")
        token_id = sparse.weights[0][0] if sparse.weights else -1
        return self.sparse.get(token_id, ())[:limit]


def _language_maps() -> tuple[
    dict[tuple[float, ...], tuple[RetrievedChunk, ...]],
    dict[int, tuple[RetrievedChunk, ...]],
]:
    pt = _chunk(key="faq/pt.md", content="prazo de atraso", score=0.9)
    es = _chunk(key="faq/es.md", content="plazo de mora", score=0.9)
    en = _chunk(key="faq/en.md", content="late fee deadline", score=0.9)
    dense: dict[tuple[float, ...], tuple[RetrievedChunk, ...]] = {
        (1.0, 0.0, 0.0): (pt,),
        (0.0, 1.0, 0.0): (es,),
        (0.0, 0.0, 1.0): (en,),
    }
    sparse: dict[int, tuple[RetrievedChunk, ...]] = {10: (pt,), 20: (es,), 30: (en,)}
    return dense, sparse


@pytest.mark.parametrize(
    ("query", "content"),
    [
        ("Qual o prazo por atraso?", "prazo de atraso"),
        ("Cual es el plazo por mora?", "plazo de mora"),
        ("What is the late fee?", "late fee deadline"),
    ],
)
async def test_hybrid_retriever_returns_expected_chunks_per_language(
    query: str,
    content: str,
) -> None:
    dense, sparse = _language_maps()
    retriever = HybridRetriever(
        FakeEmbedder(),
        FakeSparseEmbedder(),
        FakeStore(dense, sparse),
    )

    result = await retriever.retrieve(
        KnowledgeQuery(text=query, categories=("faq",), as_of=date(2026, 1, 1), limit=5),
    )

    assert result.rag_unavailable is False
    assert result.retrieval_mode == "hybrid_rrf"
    assert result.passages[0].content == content
    assert result.passages[0].dense_score is not None
    assert result.passages[0].sparse_score is not None


async def test_hybrid_retriever_fuses_weighted_scores() -> None:
    dense_a = _chunk(key="faq/a.md", content="a", score=0.9)
    dense_b = _chunk(key="faq/b.md", content="b", score=0.5)
    sparse_a = _chunk(key="faq/a.md", content="a", score=2.0)
    sparse_b = _chunk(key="faq/b.md", content="b", score=10.0)
    embedder = FakeEmbedder()
    sparse_embedder = FakeSparseEmbedder()
    store = FakeStore(
        {(1.0, 0.0, 0.0): (dense_a, dense_b)},
        {10: (sparse_a, sparse_b)},
    )
    retriever = HybridRetriever(
        embedder,
        sparse_embedder,
        store,
        fusion="weighted",
        dense_weight=0.6,
        sparse_weight=0.4,
    )

    result = await retriever.retrieve(KnowledgeQuery(text="atraso", limit=2))

    assert result.retrieval_mode == "hybrid_weighted"
    assert [passage.content for passage in result.passages] == ["b", "a"]
    assert result.passages[0].score == pytest.approx(0.7)
    assert result.passages[1].score == pytest.approx(0.62)


async def test_hybrid_retriever_degrades_when_sparse_embedding_fails() -> None:
    dense, sparse = _language_maps()
    retriever = HybridRetriever(
        FakeEmbedder(),
        FakeSparseEmbedder(fail=True),
        FakeStore(dense, sparse),
    )

    result = await retriever.retrieve(KnowledgeQuery(text="atraso", limit=5))

    assert result.rag_unavailable is False
    assert result.retrieval_mode == "dense"
    assert result.passages[0].content == "prazo de atraso"


async def test_hybrid_retriever_degrades_when_dense_embedding_fails() -> None:
    dense, sparse = _language_maps()
    retriever = HybridRetriever(
        FakeEmbedder(fail=True),
        FakeSparseEmbedder(),
        FakeStore(dense, sparse),
    )

    result = await retriever.retrieve(KnowledgeQuery(text="atraso", limit=5))

    assert result.rag_unavailable is False
    assert result.retrieval_mode == "sparse"
    assert result.passages[0].content == "prazo de atraso"


async def test_hybrid_retriever_reports_unavailable_when_both_sides_fail() -> None:
    retriever = HybridRetriever(
        FakeEmbedder(fail=True),
        FakeSparseEmbedder(fail=True),
        FakeStore(),
    )

    result = await retriever.retrieve(KnowledgeQuery(text="atraso"))

    assert result.rag_unavailable is True
    assert result.reason == "rag_unavailable"
    assert result.passages == ()


async def test_hybrid_retriever_degrades_when_one_store_query_fails() -> None:
    dense, sparse = _language_maps()
    retriever = HybridRetriever(
        FakeEmbedder(),
        FakeSparseEmbedder(),
        FakeStore(dense, sparse, fail_dense=True),
    )

    result = await retriever.retrieve(KnowledgeQuery(text="atraso", limit=5))

    assert result.rag_unavailable is False
    assert result.retrieval_mode == "sparse"
    assert result.passages[0].content == "prazo de atraso"


async def test_hybrid_retriever_respects_limit_and_filters() -> None:
    dense_a = _chunk(key="faq/a.md", content="a", score=0.9)
    dense_b = _chunk(key="faq/b.md", content="b", index=1, score=0.5)
    store = FakeStore({(1.0, 0.0, 0.0): (dense_a, dense_b)})
    retriever = HybridRetriever(FakeEmbedder(), FakeSparseEmbedder(), store)

    result = await retriever.retrieve(
        KnowledgeQuery(
            text="atraso",
            categories=("faq",),
            as_of=date(2026, 2, 1),
            limit=1,
        ),
    )

    assert len(result.passages) == 1
    assert store.filters[0].categories == ("faq",)
    assert store.filters[0].as_of == date(2026, 2, 1)


class PipelineReranker:
    model_id = "pipeline-reranker"

    def __init__(self) -> None:
        self.documents: tuple[str, ...] = ()

    async def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]:
        del query
        self.documents = documents
        return tuple(
            RerankResult(index=index, score=0.99 - index * 0.1)
            for index in range(min(top_n or len(documents), len(documents)))
        )


async def test_two_stage_pipeline_reranks_hybrid_stage_one() -> None:
    pt = _chunk(key="faq/pt.md", content="prazo de atraso", score=0.9)
    other = _chunk(key="faq/outro.md", content="outro texto", index=1, score=0.5)
    stage1 = HybridRetriever(
        FakeEmbedder(),
        FakeSparseEmbedder(),
        FakeStore(
            {(1.0, 0.0, 0.0): (pt, other)},
            {10: (pt,)},
        ),
    )
    reranker = PipelineReranker()
    retriever = TwoStageRetriever(
        stage1,
        reranker=reranker,
        rerank_enabled=True,
        top_n=1,
        timeout_seconds=1.0,
    )

    result = await retriever.retrieve(KnowledgeQuery(text="atraso", limit=5))

    assert len(result.passages) == 1
    assert result.retrieval_mode == "hybrid_rrf_reranked"
    assert result.passages[0].rerank_score == pytest.approx(0.99)
    assert reranker.documents == ("prazo de atraso", "outro texto")


def test_fuse_rrf_and_weighted_are_deterministic() -> None:
    dense = (_chunk(key="faq/a.md", content="a", score=0.9),)
    sparse = (_chunk(key="faq/b.md", content="b", score=3.0),)

    rrf = fuse_rrf(dense, sparse, rrf_k=60)
    weighted = fuse_weighted(
        dense,
        sparse,
        dense_weight=0.5,
        sparse_weight=0.5,
    )

    assert [item.chunk.document_key for item in rrf] == ["faq/a.md", "faq/b.md"]
    assert rrf[0].fused_score == pytest.approx(1.0 / 61)
    assert rrf[1].fused_score == pytest.approx(1.0 / 61)
    assert [item.chunk.document_key for item in weighted] == ["faq/b.md", "faq/a.md"]
    assert weighted[0].fused_score == pytest.approx(0.5)
    assert weighted[1].fused_score == pytest.approx(0.45)
