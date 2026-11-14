import hashlib
import os
from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paysentineliq.domain.knowledge import (
    EmbeddedChunk,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeFilter,
    Provenance,
)
from paysentineliq.infrastructure.rag.fake_embedding import (
    DeterministicHashEmbedding,
)
from paysentineliq.infrastructure.rag.models import (
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
)
from paysentineliq.infrastructure.rag.pgvector import PGVectorStore

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_DIMENSION = 8


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def test_pgvector_roundtrip_idempotency_filters_and_delete() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    embedder = DeterministicHashEmbedding(dimension=_DIMENSION)
    store = PGVectorStore(factory, dimension=_DIMENSION)
    unique = uuid4().hex
    category = f"it-rag-{unique}"
    document_key = f"{category}/doc.pdf"
    document = KnowledgeDocument(
        key=document_key,
        category=category,
        path=f"knowledge/{document_key}",
        title="Documento de teste",
        source="blog.example.com",
        provenance=Provenance.COMPILED,
        version="1",
        valid_from=date(2024, 1, 1),
        valid_until=date(2024, 12, 31),
        content_hash="a" * 64,
        pages=(),
    )
    first_texts = ("conteudo alfa", "conteudo beta")
    first_vectors = await embedder.embed(first_texts)
    first_chunks = tuple(
        EmbeddedChunk(
            chunk=KnowledgeChunk(
                document_key=document_key,
                index=index,
                section="page 1",
                position=index,
                content=text,
                content_hash=_hash(text),
            ),
            embedding=vector,
        )
        for index, (text, vector) in enumerate(
            zip(first_texts, first_vectors, strict=True),
        )
    )

    try:
        inserted = await store.upsert_document(document, first_chunks)
        assert inserted.skipped is False
        assert inserted.chunks_written == 2

        skipped = await store.upsert_document(document, first_chunks)
        assert skipped.skipped is True
        assert skipped.chunks_written == 0

        query_vector = (await embedder.embed(("conteudo alfa",)))[0]
        passages = await store.query(
            query_vector,
            limit=1,
            filters=KnowledgeFilter(
                categories=(category,),
                provenance=(Provenance.COMPILED,),
                as_of=date(2024, 6, 1),
            ),
        )
        assert len(passages) == 1
        assert passages[0].document_key == document_key
        assert passages[0].content == "conteudo alfa"
        assert passages[0].authoritative is False
        assert passages[0].score == pytest.approx(1.0, abs=1e-5)

        expired = await store.query(
            query_vector,
            limit=5,
            filters=KnowledgeFilter(
                categories=(category,),
                as_of=date(2025, 6, 1),
            ),
        )
        assert expired == ()

        second_texts = ("conteudo gama",)
        second_vectors = await embedder.embed(second_texts)
        second_chunks = tuple(
            EmbeddedChunk(
                chunk=KnowledgeChunk(
                    document_key=document_key,
                    index=0,
                    section="page 1",
                    position=0,
                    content=text,
                    content_hash=_hash(text),
                ),
                embedding=second_vectors[0],
            )
            for text in second_texts
        )
        modified = replace(document, content_hash="c" * 64)
        replaced = await store.upsert_document(modified, second_chunks)
        assert replaced.skipped is False
        assert replaced.chunks_written == 1
        assert replaced.chunks_deleted == 2

        async with factory() as session:
            documents = await session.scalar(
                select(func.count())
                .select_from(KnowledgeDocumentModel)
                .where(KnowledgeDocumentModel.document_key == document_key),
            )
            chunks = await session.scalar(
                select(func.count())
                .select_from(KnowledgeChunkModel)
                .join(
                    KnowledgeDocumentModel,
                    KnowledgeChunkModel.document_id == KnowledgeDocumentModel.id,
                )
                .where(KnowledgeDocumentModel.document_key == document_key),
            )
        assert documents == 1
        assert chunks == 1

        await store.delete_document(document_key)
        assert (
            await store.query(
                query_vector,
                limit=5,
                filters=KnowledgeFilter(categories=(category,)),
            )
        ) == ()
    finally:
        await store.delete_document(document_key)
        await engine.dispose()
