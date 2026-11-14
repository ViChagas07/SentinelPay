"""analysis queue state, idempotency and notification outbox

Revision ID: 0006_analysis_queue
Revises: 0005_analyses
Create Date: 2026-11-14 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006_analysis_queue"
down_revision = "0005_analyses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "analyses",
        sa.Column("idempotency_request_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "analyses",
        sa.Column("task_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "analyses",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_analyses_owner_idempotency",
        "analyses",
        ["owner_id", "idempotency_key"],
    )
    op.create_index(
        "ix_analyses_owner_created_at",
        "analyses",
        ["owner_id", "created_at"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_analyses_status",
        "analyses",
        "status IN ('queued', 'processing', 'completed', 'failed', 'degraded')",
    )

    op.create_table(
        "notifications",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column(
            "payload",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="pending",
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
        sa.CheckConstraint(
            "type IN ('analysis_completed')",
            name="ck_notifications_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'dispatched', 'failed')",
            name="ck_notifications_status",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_owner_id",
        "notifications",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_analysis_id",
        "notifications",
        ["analysis_id"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_status",
        "notifications",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_owner_created_at",
        "notifications",
        ["owner_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_owner_created_at", table_name="notifications")
    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_analysis_id", table_name="notifications")
    op.drop_index("ix_notifications_owner_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_constraint("ck_analyses_status", "analyses", type_="check")
    op.drop_index("ix_analyses_owner_created_at", table_name="analyses")
    op.drop_constraint(
        "uq_analyses_owner_idempotency",
        "analyses",
        type_="unique",
    )
    op.drop_column("analyses", "processing_started_at")
    op.drop_column("analyses", "task_id")
    op.drop_column("analyses", "idempotency_request_hash")
    op.drop_column("analyses", "idempotency_key")
