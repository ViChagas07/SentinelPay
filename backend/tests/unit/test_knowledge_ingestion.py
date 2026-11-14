import pytest

from paysentineliq.application.commands.knowledge_ingestion import (
    IngestKnowledgeCommand,
    IngestKnowledgeHandler,
)
from paysentineliq.application.errors import (
    EmbeddingUnavailableError,
    RagUnavailableError,
)
from paysentineliq.application.ports.knowledge_source import SourceScan
from paysentineliq.domain.knowledge import (
    EmbeddedChunk,
    KnowledgeDocument,
    KnowledgeFilter,
    Provenance,
    RetrievedChunk,
    SourcePage,
    UpsertResult,
)

pytestmark = pytest.mark.unit


def _document(
    path: str = "knowledge/faq/faq.pdf",
    *,
    key: str = "faq/faq.pdf",
    category: str = "faq",
) -> KnowledgeDocument:
    return KnowledgeDocument(
        key=key,
        category=category,
        path=path,
        title="FAQ",
        source="unknown",
        provenance=Provenance.UNKNOWN,
        version=None,
        valid_from=None,
        valid_until=None,
        content_hash="a" * 64,
        pages=(SourcePage(number=1, text="Conteudo da base."),),
        format="pdf",
    )


class FakeSource:
    def __init__(
        self,
        documents: tuple[KnowledgeDocument, ...],
        *,
        warnings: tuple[str, ...] = ("weird",),
    ) -> None:
        self._documents = documents
        self._warnings = warnings

    def scan(self) -> SourceScan:
        return SourceScan(
            documents=self._documents,
            skipped_directories=self._warnings,
        )


class FakeEmbedder:
    dimension = 4

    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self._fail = fail

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.calls += 1
        if self._fail:
            raise EmbeddingUnavailableError("offline")
        return tuple((1.0, 0.0, 0.0, 0.0) for _ in texts)


class FakeStore:
    def __init__(self, *, fail_key: str | None = None, skip: bool = False) -> None:
        self.calls: list[tuple[str, int]] = []
        self._fail_key = fail_key
        self._skip = skip

    async def upsert_document(
        self,
        document: KnowledgeDocument,
        chunks: tuple[EmbeddedChunk, ...],
    ) -> UpsertResult:
        self.calls.append((document.key, len(chunks)))
        if self._fail_key == document.key:
            raise RagUnavailableError("store offline")
        return UpsertResult(
            document_key=document.key,
            skipped=self._skip,
            chunks_written=0 if self._skip else len(chunks),
            chunks_deleted=0,
        )

    async def delete_document(self, document_key: str) -> None:
        return None

    async def query(
        self,
        embedding: tuple[float, ...],
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]:
        return ()


async def test_valid_ingestion_reports_documents_chunks_and_warnings() -> None:
    source = FakeSource((_document(),))
    embedder = FakeEmbedder()
    store = FakeStore()
    handler = IngestKnowledgeHandler(source, embedder, store)

    report = await handler.handle(IngestKnowledgeCommand())

    assert report.documents == 1
    assert report.chunks >= 1
    assert report.skipped_documents == 0
    assert report.failures == ()
    assert report.warnings == ("weird",)
    assert report.elapsed_seconds >= 0
    assert embedder.calls == 1
    assert len(store.calls) == 1


async def test_user_document_is_never_embedded_or_indexed() -> None:
    source = FakeSource(
        (_document(path="users/u1/doc.pdf", key="users/u1/doc.pdf", category="users"),),
    )
    embedder = FakeEmbedder()
    store = FakeStore()
    handler = IngestKnowledgeHandler(source, embedder, store)

    report = await handler.handle(IngestKnowledgeCommand())

    assert report.documents == 0
    assert len(report.failures) == 1
    assert report.failures[0].reason == "outside_knowledge_root"
    assert embedder.calls == 0
    assert store.calls == []


async def test_failure_on_one_document_does_not_stop_the_rest() -> None:
    source = FakeSource(
        (
            _document(key="faq/a.pdf", path="knowledge/faq/a.pdf"),
            _document(key="faq/b.pdf", path="knowledge/faq/b.pdf"),
        ),
    )
    store = FakeStore(fail_key="faq/a.pdf")
    handler = IngestKnowledgeHandler(source, FakeEmbedder(), store)

    report = await handler.handle(IngestKnowledgeCommand())

    assert report.documents == 1
    assert len(report.failures) == 1
    assert report.failures[0].document_key == "faq/a.pdf"
    assert len(store.calls) == 2


async def test_skipped_document_does_not_count_chunks() -> None:
    source = FakeSource((_document(),))
    store = FakeStore(skip=True)
    handler = IngestKnowledgeHandler(source, FakeEmbedder(), store)

    report = await handler.handle(IngestKnowledgeCommand())

    assert report.documents == 1
    assert report.skipped_documents == 1
    assert report.chunks == 0


async def test_embedding_failure_is_reported_without_content() -> None:
    source = FakeSource((_document(),))
    handler = IngestKnowledgeHandler(source, FakeEmbedder(fail=True), FakeStore())

    report = await handler.handle(IngestKnowledgeCommand())

    assert report.documents == 0
    assert len(report.failures) == 1
    assert report.failures[0].reason == "embedding_unavailable"
