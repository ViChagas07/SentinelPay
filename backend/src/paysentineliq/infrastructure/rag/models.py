from datetime import date
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from paysentineliq.domain.ports.retrieval import DENSE_EMBEDDING_DIMENSION
from paysentineliq.infrastructure.config import get_settings
from paysentineliq.infrastructure.db.base import Base

_EMBEDDING_DIM = get_settings().embedding_dim or 8


class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"

    document_key: Mapped[str] = mapped_column(
        String(512),
        unique=True,
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    chunks: Mapped[list["KnowledgeChunkModel"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class KnowledgeChunkModel(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_knowledge_chunks_document_index",
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(512), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(_EMBEDDING_DIM), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    document: Mapped[KnowledgeDocumentModel] = relationship(back_populates="chunks")


class KnowledgeHybridChunkModel(Base):
    __tablename__ = "knowledge_hybrid_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_knowledge_hybrid_chunks_document_index",
        ),
        Index(
            "ix_knowledge_hybrid_chunks_dense_hnsw",
            "dense_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"dense_embedding": "vector_cosine_ops"},
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(512), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dense_embedding: Mapped[Any] = mapped_column(
        Vector(DENSE_EMBEDDING_DIMENSION),
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )


class KnowledgeHybridSparseTermModel(Base):
    __tablename__ = "knowledge_hybrid_chunk_sparse_terms"
    __table_args__ = (
        UniqueConstraint(
            "chunk_id",
            "token_id",
            name="uq_knowledge_hybrid_sparse_chunk_token",
        ),
        CheckConstraint(
            "token_id >= 0",
            name="ck_knowledge_hybrid_sparse_token_id",
        ),
        CheckConstraint(
            "weight > 0",
            name="ck_knowledge_hybrid_sparse_weight",
        ),
    )

    chunk_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("knowledge_hybrid_chunks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    token_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
