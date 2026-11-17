"""hybrid knowledge retrieval vectors

Revision ID: 0010_hybrid_retrieval
Revises: 0009_notification_rollback
Create Date: 2026-11-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010_hybrid_retrieval"
down_revision = "0009_notification_rollback"
branch_labels = None
depends_on = None

_DENSE_DIMENSION = 1024


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_hybrid_chunks",
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
        sa.Column("dense_embedding", Vector(_DENSE_DIMENSION), nullable=False),
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
            name="uq_knowledge_hybrid_chunks_document_index",
        ),
    )
    op.create_index(
        "ix_knowledge_hybrid_chunks_document_id",
        "knowledge_hybrid_chunks",
        ["document_id"],
        unique=False,
    )
    op.execute(
        "CREATE INDEX ix_knowledge_hybrid_chunks_dense_hnsw "
        "ON knowledge_hybrid_chunks USING hnsw (dense_embedding vector_cosine_ops)",
    )
    op.create_table(
        "knowledge_hybrid_chunk_sparse_terms",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("token_id", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
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
        sa.CheckConstraint(
            "token_id >= 0",
            name="ck_knowledge_hybrid_sparse_token_id",
        ),
        sa.CheckConstraint(
            "weight > 0",
            name="ck_knowledge_hybrid_sparse_weight",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["knowledge_hybrid_chunks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chunk_id",
            "token_id",
            name="uq_knowledge_hybrid_sparse_chunk_token",
        ),
    )
    op.create_index(
        "ix_knowledge_hybrid_chunk_sparse_terms_chunk_id",
        "knowledge_hybrid_chunk_sparse_terms",
        ["chunk_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_hybrid_chunk_sparse_terms_token_id",
        "knowledge_hybrid_chunk_sparse_terms",
        ["token_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_hybrid_chunk_sparse_terms_token_id",
        table_name="knowledge_hybrid_chunk_sparse_terms",
    )
    op.drop_index(
        "ix_knowledge_hybrid_chunk_sparse_terms_chunk_id",
        table_name="knowledge_hybrid_chunk_sparse_terms",
    )
    op.drop_table("knowledge_hybrid_chunk_sparse_terms")
    op.drop_index(
        "ix_knowledge_hybrid_chunks_dense_hnsw",
        table_name="knowledge_hybrid_chunks",
    )
    op.drop_index(
        "ix_knowledge_hybrid_chunks_document_id",
        table_name="knowledge_hybrid_chunks",
    )
    op.drop_table("knowledge_hybrid_chunks")
