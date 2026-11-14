"""knowledge rag documents and chunks

Revision ID: 0004_knowledge_chunks
Revises: 0003_documents
Create Date: 2026-11-14 00:00:00.000000

"""

import os

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_knowledge_chunks"
down_revision = "0003_documents"
branch_labels = None
depends_on = None


def _embedding_dim() -> int:
    raw = os.environ.get("EMBEDDING_DIM", "")
    try:
        dimension = int(raw)
    except ValueError as exc:
        raise RuntimeError(
            "EMBEDDING_DIM must be a positive integer before applying 0004_knowledge_chunks",
        ) from exc
    if dimension <= 0:
        raise RuntimeError(
            "EMBEDDING_DIM must be a positive integer before applying 0004_knowledge_chunks",
        )
    return dimension


def upgrade() -> None:
    dimension = _embedding_dim()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_documents",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_key", sa.String(length=512), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("provenance", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=128), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "metadata",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_key"),
    )
    op.create_index(
        "ix_knowledge_documents_category",
        "knowledge_documents",
        ["category"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_documents_content_hash",
        "knowledge_documents",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_documents_provenance",
        "knowledge_documents",
        ["provenance"],
        unique=False,
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(length=512), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(dimension), nullable=False),
        sa.Column(
            "metadata",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["knowledge_documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_knowledge_chunks_document_index",
        ),
    )
    op.create_index(
        "ix_knowledge_chunks_document_id",
        "knowledge_chunks",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
