import hashlib

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paysentineliq.domain.knowledge import (
    EmbeddedChunk,
    KnowledgeDocument,
    KnowledgeFilter,
    Provenance,
    RetrievedChunk,
    UpsertResult,
)
from paysentineliq.infrastructure.rag.models import (
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
)


def _chunk_set_hash(chunks: tuple[EmbeddedChunk, ...]) -> str:
    canonical = "\n".join(chunk.chunk.content_hash for chunk in chunks)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PGVectorStore:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        dimension: int,
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._session_factory = session_factory
        self._dimension = dimension

    def _validate(self, embedding: tuple[float, ...]) -> None:
        if len(embedding) != self._dimension:
            raise ValueError("embedding dimension does not match the vector column")

    async def upsert_document(
        self,
        document: KnowledgeDocument,
        chunks: tuple[EmbeddedChunk, ...],
    ) -> UpsertResult:
        if not chunks:
            raise ValueError("document must have at least one chunk")
        for embedded in chunks:
            self._validate(embedded.embedding)
            if embedded.chunk.document_key != document.key:
                raise ValueError("chunk document_key does not match document")
        chunk_set_hash = _chunk_set_hash(chunks)

        async with self._session_factory() as session:
            async with session.begin():
                existing = await session.scalar(
                    select(KnowledgeDocumentModel).where(
                        KnowledgeDocumentModel.document_key == document.key,
                    ),
                )
                if (
                    existing is not None
                    and existing.content_hash == document.content_hash
                    and existing.metadata_.get("chunk_set_hash") == chunk_set_hash
                ):
                    return UpsertResult(
                        document_key=document.key,
                        skipped=True,
                        chunks_written=0,
                        chunks_deleted=0,
                    )

                deleted = 0
                if existing is not None:
                    result = await session.execute(
                        delete(KnowledgeChunkModel).where(
                            KnowledgeChunkModel.document_id == existing.id,
                        ),
                    )
                    deleted = getattr(result, "rowcount", 0) or 0
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
                        "source_format": document.format,
                        "chunk_count": len(chunks),
                        "chunk_set_hash": chunk_set_hash,
                    }
                else:
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
                            "chunk_count": len(chunks),
                            "chunk_set_hash": chunk_set_hash,
                        },
                    )
                    session.add(existing)
                    await session.flush()

                for embedded in chunks:
                    chunk = embedded.chunk
                    session.add(
                        KnowledgeChunkModel(
                            document_id=existing.id,
                            chunk_index=chunk.index,
                            section=chunk.section,
                            position=chunk.position,
                            content=chunk.content,
                            content_hash=chunk.content_hash,
                            embedding=list(embedded.embedding),
                            metadata_={},
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
            await session.execute(
                delete(KnowledgeDocumentModel).where(
                    KnowledgeDocumentModel.document_key == document_key,
                ),
            )

    async def query(
        self,
        embedding: tuple[float, ...],
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[RetrievedChunk, ...]:
        self._validate(embedding)
        if limit <= 0:
            raise ValueError("limit must be positive")

        distance = KnowledgeChunkModel.embedding.cosine_distance(list(embedding))
        statement = (
            select(KnowledgeChunkModel, KnowledgeDocumentModel, distance.label("distance"))
            .join(
                KnowledgeDocumentModel,
                KnowledgeChunkModel.document_id == KnowledgeDocumentModel.id,
            )
            .order_by(distance)
            .limit(limit)
        )
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

        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()

        return tuple(
            RetrievedChunk(
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
                score=1.0 - float(row_distance),
            )
            for chunk, document, row_distance in rows
        )
