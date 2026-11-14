"""documents metadata

Revision ID: 0003_documents
Revises: 0002_auth
Create Date: 2026-11-14 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0003_documents"
down_revision = "0002_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("s3_key", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column(
            "original_name_sanitized",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('bank_slip', 'payslip', 'receipt')",
            name="ck_documents_kind",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_documents_owner_id",
        "documents",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        "ix_documents_s3_key",
        "documents",
        ["s3_key"],
        unique=True,
    )
    op.create_index(
        "ix_documents_sha256",
        "documents",
        ["sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("documents")
