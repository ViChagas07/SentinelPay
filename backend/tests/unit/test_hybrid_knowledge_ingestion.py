import pytest

from paysentineliq.application.commands.hybrid_knowledge_ingestion import (
    HybridKnowledgeIngestionHandler,
)
from paysentineliq.application.commands.knowledge_ingestion import (
    IngestKnowledgeCommand,
)
from paysentineliq.application.ports.knowledge_source import SourceScan
from paysentineliq.domain.knowledge import (
    KnowledgeDocument,
    KnowledgeFilter,
    Provenance,
    RetrievedChunk,
    SourcePage,
    UpsertResult,
)
from paysentineliq.domain.ports.retrieval import (
    HybridEmbeddedChunk,
    SparseVector,
)

pytestmark = pytest.mark.unit


def _document(
    *,
    key: str = "faq/a.pdf",
    path: str = "knowledge/faq/a.pdf",
    category: str = "faq",
    content: str = "Conteudo A",
) -> KnowledgeDocument:
    return KnowledgeDocument(
        key=key,
        category=category,
        path=path,
        title="Documento",
        source="oficial",
        provenance=Provenance.OFFICIAL,
        version="1",
        valid_from=None,
        valid_until=None,
        content_hash="a" * 64,
        pages=(SourcePage(number=1, text=content),),
        format="pdf",
    )


class FakeSource:
    def __init__(self, documents: tuple[KnowledgeDocument, ...]) -> None:
        self._documents = documents

    def scan(self) -> SourceScan:
        return SourceScan(documents=self._documents, skipped_directories=("ignored",))


class FakeEmbedder:
    dimension = 3
    model_id = "fake-dense"

    def __init__(self, *, count_offset: int = 0, bad_dimension: bool = False) -> None:
        self.dense_calls = 0
        self.sparse_calls = 0
        self.hybrid_calls = 0
        self._count_offset = count_offset
        self._bad_dimension = bad_dimension

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.dense_calls += 1
        size = 2 if self._bad_dimension else self.dimension
        vectors = [tuple([1.0] * size) for _ in texts]
        return tuple(vectors[: len(texts) + self._count_offset])

    async def embed_sparse(self, texts: tuple[str, ...]) -> tuple[SparseVector, ...]:
        self.sparse_calls += 1
        return tuple(SparseVector(((index + 1, 1.0),)) for index, _ in enumerate(texts))

    async def embed_hybrid(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[tuple[float, ...], ...], tuple[SparseVector, ...]]:
        self.hybrid_calls += 1
        return await self.embed(texts), await self.embed_sparse(texts)


class FakeStore:
    def __init__(self, *, fail_key: str | None = None) -> None:
        self.documents: dict[str, tuple[str, ...]] = {}
        self.models: dict[str, str] = {}
        self.writes = 0
        self._fail_key = fail_key

    async def upsert_hybrid_document(
        self,
        document: KnowledgeDocument,
        chunks: tuple[HybridEmbeddedChunk, ...],
        *,
        embedding_model: str = "",
    ) -> UpsertResult:
        if self._fail_key == document.key:
            raise RuntimeError("store offline")
        hashes = tuple(item.chunk.content_hash for item in chunks)
        if (
            self.documents.get(document.key) == hashes
            and self.models.get(document.key) == embedding_model
        ):
            return UpsertResult(
                document_key=document.key,
                skipped=True,
                chunks_written=0,
                chunks_deleted=0,
            )
        self.documents[document.key] = hashes
        self.models[document.key] = embedding_model
        self.writes += 1
        return UpsertResult(
            document_key=document.key,
            skipped=False,
            chunks_written=len(chunks),
            chunks_deleted=0,
        )

    async def delete_document(self, document_key: str) -> None:
        raise AssertionError("not used")

    async def dense_query(
        self,
        embedding: tuple[float, ...],
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]:
        raise AssertionError("not used")

    async def sparse_query(
        self,
        sparse: SparseVector,
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]:
        raise AssertionError("not used")


async def test_hybrid_reindex_is_idempotent() -> None:
    source = FakeSource((_document(),))
    embedder = FakeEmbedder()
    store = FakeStore()
    handler = HybridKnowledgeIngestionHandler(source, embedder, embedder, store)

    first = await handler.handle(IngestKnowledgeCommand())
    second = await handler.handle(IngestKnowledgeCommand())

    assert first.documents == 1
    assert first.chunks >= 1
    assert first.skipped_documents == 0
    assert second.documents == 1
    assert second.chunks == 0
    assert second.skipped_documents == 1
    assert store.writes == 1
    assert len(store.documents) == 1


async def test_hybrid_reindex_rewrites_when_embedding_model_changes() -> None:
    source = FakeSource((_document(),))
    embedder = FakeEmbedder()
    store = FakeStore()
    handler = HybridKnowledgeIngestionHandler(source, embedder, embedder, store)

    await handler.handle(IngestKnowledgeCommand())
    embedder.model_id = "fake-dense-v2"
    second = await handler.handle(IngestKnowledgeCommand())

    assert second.skipped_documents == 0
    assert store.writes == 2
    assert store.models["faq/a.pdf"] == "fake-dense-v2"


async def test_hybrid_reindex_uses_single_hybrid_embedding_pass() -> None:
    source = FakeSource((_document(),))
    embedder = FakeEmbedder()
    store = FakeStore()
    handler = HybridKnowledgeIngestionHandler(
        source,
        embedder,
        embedder,
        store,
        hybrid_embedder=embedder,
    )

    await handler.handle(IngestKnowledgeCommand())

    assert embedder.hybrid_calls == 1
    assert embedder.dense_calls == 1
    assert embedder.sparse_calls == 1


async def test_hybrid_reindex_reports_embedding_count_mismatch() -> None:
    source = FakeSource((_document(),))
    embedder = FakeEmbedder(count_offset=-1)
    store = FakeStore()
    handler = HybridKnowledgeIngestionHandler(source, embedder, embedder, store)

    report = await handler.handle(IngestKnowledgeCommand())

    assert report.documents == 0
    assert report.failures[0].reason == "embedding_dimension_mismatch"
    assert store.writes == 0


async def test_hybrid_reindex_reports_wrong_embedding_dimension() -> None:
    source = FakeSource((_document(),))
    embedder = FakeEmbedder(bad_dimension=True)
    store = FakeStore()
    handler = HybridKnowledgeIngestionHandler(source, embedder, embedder, store)

    report = await handler.handle(IngestKnowledgeCommand())

    assert report.documents == 0
    assert report.failures[0].reason == "embedding_dimension_mismatch"


async def test_hybrid_reindex_never_embeds_user_documents() -> None:
    source = FakeSource(
        (_document(path="users/u1/doc.pdf", key="users/u1/doc.pdf", category="users"),),
    )
    embedder = FakeEmbedder()
    store = FakeStore()
    handler = HybridKnowledgeIngestionHandler(source, embedder, embedder, store)

    report = await handler.handle(IngestKnowledgeCommand())

    assert report.documents == 0
    assert report.failures[0].reason == "outside_knowledge_root"
    assert embedder.dense_calls == 0
    assert store.writes == 0


async def test_hybrid_reindex_continues_after_one_document_failure() -> None:
    source = FakeSource(
        (
            _document(key="faq/a.pdf", path="knowledge/faq/a.pdf"),
            _document(key="faq/b.pdf", path="knowledge/faq/b.pdf"),
        ),
    )
    embedder = FakeEmbedder()
    store = FakeStore(fail_key="faq/a.pdf")
    handler = HybridKnowledgeIngestionHandler(source, embedder, embedder, store)

    report = await handler.handle(IngestKnowledgeCommand())

    assert report.documents == 1
    assert len(report.failures) == 1
    assert report.failures[0].document_key == "faq/a.pdf"
    assert store.writes == 1
