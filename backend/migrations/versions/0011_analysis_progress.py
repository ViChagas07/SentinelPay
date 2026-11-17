"""analysis progress and cooperative cancellation

Revision ID: 0011_analysis_progress
Revises: 0010_hybrid_retrieval
Create Date: 2026-11-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0011_analysis_progress"
down_revision = "0010_hybrid_retrieval"
branch_labels = None
depends_on = None

_NEW_STATUSES = "'queued', 'running', 'cancelling', 'cancelled', 'completed', 'failed', 'degraded'"
_OLD_STATUSES = "'queued', 'processing', 'completed', 'failed', 'degraded'"


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column(
            "progress_percent",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "analyses",
        sa.Column("current_stage", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "analyses",
        sa.Column("stage_detail", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "analyses",
        sa.Column("stage_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "analyses",
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "analyses",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_analyses_progress_percent",
        "analyses",
        "progress_percent >= 0 AND progress_percent <= 100",
    )
    op.drop_constraint("ck_analyses_status", "analyses", type_="check")
    op.execute("UPDATE analyses SET status = 'running' WHERE status = 'processing'")
    op.create_check_constraint(
        "ck_analyses_status",
        "analyses",
        f"status IN ({_NEW_STATUSES})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_analyses_status", "analyses", type_="check")
    op.execute(
        "UPDATE analyses SET status = 'failed' WHERE status IN ('cancelling', 'cancelled')",
    )
    op.execute("UPDATE analyses SET status = 'processing' WHERE status = 'running'")
    op.create_check_constraint(
        "ck_analyses_status",
        "analyses",
        f"status IN ({_OLD_STATUSES})",
    )
    op.drop_constraint("ck_analyses_progress_percent", "analyses", type_="check")
    op.drop_column("analyses", "cancelled_at")
    op.drop_column("analyses", "cancel_requested_at")
    op.drop_column("analyses", "stage_started_at")
    op.drop_column("analyses", "stage_detail")
    op.drop_column("analyses", "current_stage")
    op.drop_column("analyses", "progress_percent")
