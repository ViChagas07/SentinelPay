import hashlib
import os
from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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
from paysentineliq.infrastructure.rag.pgvector import PGVectorStore
from paysentineliq.infrastructure.rag.pgvector_hybrid import PGVectorHybridStore

pytestmark = [pytest.mark.integration, pytest.mark.docker]


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _dense(index: int) -> tuple[float, ...]:
    vector = [0.0] * DENSE_EMBEDDING_DIMENSION
    vector[index] = 1.0
    return tuple(vector)


async def test_pgvector_hybrid_roundtrip_idempotency_and_queries() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    store = PGVectorHybridStore(factory)
    unique = uuid4().hex
    category = f"it-hybrid-{unique}"
    document_key = f"{category}/doc.pdf"
    document = KnowledgeDocument(
        key=document_key,
        category=category,
        path=f"knowledge/{document_key}",
        title="Documento hibrido",
        source="oficial",
        provenance=Provenance.OFFICIAL,
        version="1",
        valid_from=date(2024, 1, 1),
        valid_until=date(2024, 12, 31),
        content_hash="a" * 64,
        pages=(),
    )
    chunks = (
        HybridEmbeddedChunk(
            chunk=KnowledgeChunk(
                document_key=document_key,
                index=0,
                section="page 1",
                position=0,
                content="conteudo alfa",
                content_hash=_hash("conteudo alfa"),
            ),
            dense_embedding=_dense(0),
            sparse_embedding=SparseVector(((10, 2.0),)),
        ),
        HybridEmbeddedChunk(
            chunk=KnowledgeChunk(
                document_key=document_key,
                index=1,
                section="page 1",
                position=1,
                content="conteudo beta",
                content_hash=_hash("conteudo beta"),
            ),
            dense_embedding=_dense(1),
            sparse_embedding=SparseVector(((20, 3.0),)),
        ),
    )

    try:
        inserted = await store.upsert_hybrid_document(
            document,
            chunks,
            embedding_model="BAAI/bge-m3",
        )
        assert inserted.skipped is False
        assert inserted.chunks_written == 2

        skipped = await store.upsert_hybrid_document(
            document,
            chunks,
            embedding_model="BAAI/bge-m3",
        )
        assert skipped.skipped is True
        assert skipped.chunks_written == 0

        dense_rows = await store.dense_query(
            _dense(0),
            limit=2,
            filters=KnowledgeFilter(
                categories=(category,),
                provenance=(Provenance.OFFICIAL,),
                as_of=date(2024, 6, 1),
            ),
        )
        assert len(dense_rows) == 2
        assert dense_rows[0].content == "conteudo alfa"
        assert dense_rows[0].score == pytest.approx(1.0, abs=1e-5)

        sparse_rows = await store.sparse_query(
            SparseVector(((20, 1.0),)),
            limit=1,
            filters=KnowledgeFilter(categories=(category,)),
        )
        assert len(sparse_rows) == 1
        assert sparse_rows[0].content == "conteudo beta"
        assert sparse_rows[0].score == pytest.approx(3.0)

        expired = await store.dense_query(
            _dense(0),
            limit=5,
            filters=KnowledgeFilter(
                categories=(category,),
                as_of=date(2025, 6, 1),
            ),
        )
        assert expired == ()

        modified_chunk = HybridEmbeddedChunk(
            chunk=KnowledgeChunk(
                document_key=document_key,
                index=0,
                section="page 1",
                position=0,
                content="conteudo gama",
                content_hash=_hash("conteudo gama"),
            ),
            dense_embedding=_dense(2),
            sparse_embedding=SparseVector(((30, 4.0),)),
        )
        modified = replace(document, content_hash="c" * 64)
        replaced = await store.upsert_hybrid_document(
            modified,
            (modified_chunk,),
            embedding_model="BAAI/bge-m3",
        )
        assert replaced.skipped is False
        assert replaced.chunks_written == 1
        assert replaced.chunks_deleted == 2

        async with factory() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT column_name, udt_name FROM information_schema.columns "
                        "WHERE table_name='knowledge_chunks' AND column_name='embedding'",
                    ),
                )
            ).first()
        assert row is not None
        assert row[1] == "vector"

        await store.delete_document(document_key)
        assert (
            await store.dense_query(
                _dense(2),
                limit=5,
                filters=KnowledgeFilter(categories=(category,)),
            )
        ) == ()
        assert (
            await store.sparse_query(
                SparseVector(((30, 1.0),)),
                limit=5,
                filters=KnowledgeFilter(categories=(category,)),
            )
        ) == ()
    finally:
        await PGVectorStore(factory, dimension=8).delete_document(document_key)
        await engine.dispose()
