import hashlib
from typing import Any
from uuid import uuid4

from sqlalchemy import Float, Integer, Select, column, delete, func, or_, select, values
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paysentineliq.domain.knowledge import (
    KnowledgeDocument,
    KnowledgeFilter,
    Provenance,
    RetrievedChunk,
    UpsertResult,
)
from paysentineliq.domain.ports.retrieval import (
    DENSE_EMBEDDING_DIMENSION,
    HybridEmbeddedChunk,
    SparseVector,
)
from paysentineliq.infrastructure.rag.models import (
    KnowledgeDocumentModel,
    KnowledgeHybridChunkModel,
    KnowledgeHybridSparseTermModel,
)


def _chunk_set_hash(chunks: tuple[HybridEmbeddedChunk, ...]) -> str:
    canonical = "\n".join(item.chunk.content_hash for item in chunks)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _apply_filters(
    statement: Select[Any],
    filters: KnowledgeFilter,
) -> Select[Any]:
    if filters.categories:
        statement = statement.where(
            KnowledgeDocumentModel.category.in_(filters.categories),
        )
    if filters.provenance:
        statement = statement.where(
            KnowledgeDocumentModel.provenance.in_(
                [provenance.value for provenance in filters.provenance],
            ),
        )
    if filters.as_of is not None:
        statement = statement.where(
            or_(
                KnowledgeDocumentModel.valid_from.is_(None),
                KnowledgeDocumentModel.valid_from <= filters.as_of,
            ),
            or_(
                KnowledgeDocumentModel.valid_until.is_(None),
                KnowledgeDocumentModel.valid_until >= filters.as_of,
            ),
        )
    return statement


def _retrieved(
    chunk: KnowledgeHybridChunkModel, document: KnowledgeDocumentModel, score: float
) -> RetrievedChunk:
    return RetrievedChunk(
        document_key=document.document_key,
        path=document.path,
        category=document.category,
        title=document.title,
        source=document.source,
        provenance=Provenance(document.provenance),
        version=document.version,
        valid_from=document.valid_from,
        valid_until=document.valid_until,
        section=chunk.section,
        content=chunk.content,
        content_hash=chunk.content_hash,
        chunk_index=chunk.chunk_index,
        score=score,
    )


class PGVectorHybridStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @property
    def dimension(self) -> int:
        return DENSE_EMBEDDING_DIMENSION

    def _validate(self, embedding: tuple[float, ...]) -> None:
        if len(embedding) != DENSE_EMBEDDING_DIMENSION:
            raise ValueError("dense embedding dimension must be 1024")

    async def upsert_hybrid_document(
        self,
        document: KnowledgeDocument,
        chunks: tuple[HybridEmbeddedChunk, ...],
        *,
        embedding_model: str = "",
    ) -> UpsertResult:
        if not chunks:
            raise ValueError("document must have at least one chunk")
        for item in chunks:
            self._validate(item.dense_embedding)
            if item.chunk.document_key != document.key:
                raise ValueError("chunk document_key does not match document")
        chunk_set_hash = _chunk_set_hash(chunks)
        expected_hashes = tuple(item.chunk.content_hash for item in chunks)

        async with self._session_factory() as session, session.begin():
            existing = await session.scalar(
                select(KnowledgeDocumentModel).where(
                    KnowledgeDocumentModel.document_key == document.key,
                ),
            )
            existing_chunks: tuple[KnowledgeHybridChunkModel, ...] = ()
            if existing is not None:
                existing_chunks = tuple(
                    (
                        await session.execute(
                            select(KnowledgeHybridChunkModel)
                            .where(KnowledgeHybridChunkModel.document_id == existing.id)
                            .order_by(KnowledgeHybridChunkModel.chunk_index),
                        )
                    )
                    .scalars()
                    .all(),
                )
                if (
                    existing.content_hash == document.content_hash
                    and tuple(item.content_hash for item in existing_chunks) == expected_hashes
                    and all(
                        item.metadata_.get("embedding_model") == embedding_model
                        for item in existing_chunks
                    )
                ):
                    return UpsertResult(
                        document_key=document.key,
                        skipped=True,
                        chunks_written=0,
                        chunks_deleted=0,
                    )

            deleted = len(existing_chunks)
            if existing is None:
                existing = KnowledgeDocumentModel(
                    document_key=document.key,
                    category=document.category,
                    path=document.path,
                    title=document.title,
                    source=document.source,
                    provenance=document.provenance.value,
                    version=document.version,
                    valid_from=document.valid_from,
                    valid_until=document.valid_until,
                    content_hash=document.content_hash,
                    metadata_={
                        "source_format": document.format,
                        "hybrid_chunk_count": len(chunks),
                        "hybrid_chunk_set_hash": chunk_set_hash,
                    },
                )
                session.add(existing)
                await session.flush()
            else:
                existing.category = document.category
                existing.path = document.path
                existing.title = document.title
                existing.source = document.source
                existing.provenance = document.provenance.value
                existing.version = document.version
                existing.valid_from = document.valid_from
                existing.valid_until = document.valid_until
                existing.content_hash = document.content_hash
                existing.metadata_ = {
                    **(existing.metadata_ or {}),
                    "source_format": document.format,
                    "hybrid_chunk_count": len(chunks),
                    "hybrid_chunk_set_hash": chunk_set_hash,
                }
                if existing_chunks:
                    await session.execute(
                        delete(KnowledgeHybridChunkModel).where(
                            KnowledgeHybridChunkModel.document_id == existing.id,
                        ),
                    )

            for item in chunks:
                chunk_id = uuid4()
                chunk = item.chunk
                session.add(
                    KnowledgeHybridChunkModel(
                        id=chunk_id,
                        document_id=existing.id,
                        chunk_index=chunk.index,
                        section=chunk.section,
                        position=chunk.position,
                        content=chunk.content,
                        content_hash=chunk.content_hash,
                        dense_embedding=list(item.dense_embedding),
                        metadata_={"embedding_model": embedding_model},
                    ),
                )
                for token_id, weight in item.sparse_embedding.weights:
                    session.add(
                        KnowledgeHybridSparseTermModel(
                            chunk_id=chunk_id,
                            token_id=token_id,
                            weight=weight,
                        ),
                    )
        return UpsertResult(
            document_key=document.key,
            skipped=False,
            chunks_written=len(chunks),
            chunks_deleted=deleted,
        )

    async def delete_document(self, document_key: str) -> None:
        async with self._session_factory() as session, session.begin():
            document_id = await session.scalar(
                select(KnowledgeDocumentModel.id).where(
                    KnowledgeDocumentModel.document_key == document_key,
                ),
            )
            if document_id is not None:
                await session.execute(
                    delete(KnowledgeHybridChunkModel).where(
                        KnowledgeHybridChunkModel.document_id == document_id,
                    ),
                )

    async def dense_query(
        self,
        embedding: tuple[float, ...],
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]:
        self._validate(embedding)
        if limit <= 0:
            raise ValueError("limit must be positive")
        distance = KnowledgeHybridChunkModel.dense_embedding.cosine_distance(
            list(embedding),
        )
        statement = (
            select(
                KnowledgeHybridChunkModel,
                KnowledgeDocumentModel,
                distance.label("distance"),
            )
            .join(
                KnowledgeDocumentModel,
                KnowledgeHybridChunkModel.document_id == KnowledgeDocumentModel.id,
            )
            .order_by(distance)
            .limit(limit)
        )
        statement = _apply_filters(statement, filters)
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()
        return tuple(
            _retrieved(chunk, document, 1.0 - float(row_distance))
            for chunk, document, row_distance in rows
        )

    async def sparse_query(
        self,
        sparse: SparseVector,
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if not sparse.weights:
            return ()
        query_terms = values(
            column("token_id", Integer),
            column("query_weight", Float),
            name="query_terms",
        ).data([(token_id, weight) for token_id, weight in sparse.weights])
        term_scores = (
            select(
                KnowledgeHybridSparseTermModel.chunk_id.label("chunk_id"),
                func.sum(
                    KnowledgeHybridSparseTermModel.weight * query_terms.c.query_weight,
                ).label("score"),
            )
            .join(
                query_terms,
                query_terms.c.token_id == KnowledgeHybridSparseTermModel.token_id,
            )
            .group_by(KnowledgeHybridSparseTermModel.chunk_id)
            .subquery()
        )
        statement = (
            select(
                KnowledgeHybridChunkModel,
                KnowledgeDocumentModel,
                term_scores.c.score,
            )
            .join(
                term_scores,
                term_scores.c.chunk_id == KnowledgeHybridChunkModel.id,
            )
            .join(
                KnowledgeDocumentModel,
                KnowledgeHybridChunkModel.document_id == KnowledgeDocumentModel.id,
            )
            .order_by(term_scores.c.score.desc())
            .limit(limit)
        )
        statement = _apply_filters(statement, filters)
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()
        return tuple(_retrieved(chunk, document, float(score)) for chunk, document, score in rows)
