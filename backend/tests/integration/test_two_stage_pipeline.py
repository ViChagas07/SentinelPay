import hashlib
import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paysentineliq.application.queries.hybrid_retrieval import HybridRetriever
from paysentineliq.application.queries.knowledge_retrieval import KnowledgeQuery
from paysentineliq.application.queries.two_stage_retrieval import TwoStageRetriever
from paysentineliq.domain.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    Provenance,
)
from paysentineliq.domain.ports.retrieval import (
    DENSE_EMBEDDING_DIMENSION,
    HybridEmbeddedChunk,
    RerankResult,
    SparseVector,
)
from paysentineliq.infrastructure.rag.pgvector import PGVectorStore
from paysentineliq.infrastructure.rag.pgvector_hybrid import PGVectorHybridStore

pytestmark = [pytest.mark.integration, pytest.mark.docker]


def _dense(index: int) -> tuple[float, ...]:
    vector = [0.0] * DENSE_EMBEDDING_DIMENSION
    vector[index] = 1.0
    return tuple(vector)


class FakeEmbedder:
    dimension = DENSE_EMBEDDING_DIMENSION
    model_id = "fake-bge"

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple(_dense(0) for _ in texts)

    async def embed_sparse(self, texts: tuple[str, ...]) -> tuple[SparseVector, ...]:
        return tuple(SparseVector(((10, 1.0),)) for _ in texts)

    async def embed_hybrid(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[tuple[float, ...], ...], tuple[SparseVector, ...]]:
        return await self.embed(texts), await self.embed_sparse(texts)


class FakeReranker:
    model_id = "fake-reranker"

    async def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]:
        del query
        return tuple(
            RerankResult(index=index, score=0.9 - index * 0.1)
            for index in range(min(top_n or len(documents), len(documents)))
        )


async def test_full_two_stage_pipeline_against_pgvector() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    store = PGVectorHybridStore(factory)
    unique = uuid4().hex
    category = f"it-twostage-{unique}"
    document_key = f"{category}/doc.pdf"
    content = "conteudo reranqueavel"
    document = KnowledgeDocument(
        key=document_key,
        category=category,
        path=f"knowledge/{document_key}",
        title="Documento dois estagios",
        source="oficial",
        provenance=Provenance.OFFICIAL,
        version="1",
        valid_from=date(2024, 1, 1),
        valid_until=date(2024, 12, 31),
        content_hash="a" * 64,
        pages=(),
    )
    chunk = HybridEmbeddedChunk(
        chunk=KnowledgeChunk(
            document_key=document_key,
            index=0,
            section="page 1",
            position=0,
            content=content,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        ),
        dense_embedding=_dense(0),
        sparse_embedding=SparseVector(((10, 2.0),)),
    )
    embedder = FakeEmbedder()
    try:
        await store.upsert_hybrid_document(
            document,
            (chunk,),
            embedding_model="fake-bge",
        )
        stage1 = HybridRetriever(
            embedder,
            embedder,
            store,
            hybrid_embedder=embedder,
            default_limit=25,
        )
        retriever = TwoStageRetriever(
            stage1,
            reranker=FakeReranker(),
            rerank_enabled=True,
            top_n=1,
            timeout_seconds=1.0,
        )

        result = await retriever.retrieve(
            KnowledgeQuery(text="consulta", as_of=date(2024, 6, 1), limit=25),
        )

        assert len(result.passages) == 1
        assert result.passages[0].content == content
        assert result.passages[0].rerank_score == pytest.approx(0.9)
        assert result.retrieval_mode == "hybrid_rrf_reranked"
        assert result.rerank_applied is True
    finally:
        await PGVectorStore(factory, dimension=8).delete_document(document_key)
        await engine.dispose()
