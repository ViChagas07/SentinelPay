"""payables, reminder preferences and reminder notifications

Revision ID: 0007_payables
Revises: 0006_analysis_queue
Create Date: 2026-11-14 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007_payables"
down_revision = "0006_analysis_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payables",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
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
            "status IN ('pending_confirmation', 'pending', 'paid', 'overdue', 'dismissed')",
            name="ck_payables_status",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_id", name="uq_payables_analysis_id"),
    )
    op.create_index("ix_payables_owner_id", "payables", ["owner_id"], unique=False)
    op.create_index("ix_payables_analysis_id", "payables", ["analysis_id"], unique=False)
    op.create_index("ix_payables_due_date", "payables", ["due_date"], unique=False)
    op.create_index("ix_payables_status", "payables", ["status"], unique=False)
    op.create_index(
        "ix_payables_owner_due_date",
        "payables",
        ["owner_id", "due_date"],
        unique=False,
    )
    op.create_index(
        "ix_payables_owner_status_due",
        "payables",
        ["owner_id", "status", "due_date"],
        unique=False,
    )

    op.create_table(
        "reminder_preferences",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "offsets_days",
            JSONB(),
            server_default=sa.text("'[3, 1, 0]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "local_time",
            sa.Time(),
            server_default="09:00:00",
            nullable=False,
        ),
        sa.Column(
            "channels",
            JSONB(),
            server_default=sa.text("'[\"in_app\"]'::jsonb"),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_reminder_preferences_user_id"),
    )
    op.create_index(
        "ix_reminder_preferences_user_id",
        "reminder_preferences",
        ["user_id"],
        unique=False,
    )

    op.add_column(
        "notifications",
        sa.Column(
            "channel",
            sa.String(length=16),
            server_default="in_app",
            nullable=False,
        ),
    )
    op.add_column(
        "notifications",
        sa.Column("payable_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("reminder_due_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("reminder_offset_days", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_notifications_payable_id",
        "notifications",
        "payables",
        ["payable_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_notifications_payable_id",
        "notifications",
        ["payable_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_notifications_payable_reminder",
        "notifications",
        ["payable_id", "reminder_due_date", "reminder_offset_days", "channel"],
    )
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.drop_constraint("ck_notifications_status", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type",
        "notifications",
        "type IN ('analysis_completed', 'payable_due_reminder')",
    )
    op.create_check_constraint(
        "ck_notifications_status",
        "notifications",
        "status IN ('pending', 'dispatched', 'failed', 'cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_notifications_status", "notifications", type_="check")
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type",
        "notifications",
        "type IN ('analysis_completed')",
    )
    op.create_check_constraint(
        "ck_notifications_status",
        "notifications",
        "status IN ('pending', 'dispatched', 'failed')",
    )
    op.drop_constraint(
        "uq_notifications_payable_reminder",
        "notifications",
        type_="unique",
    )
    op.drop_index("ix_notifications_payable_id", table_name="notifications")
    op.drop_constraint("fk_notifications_payable_id", "notifications", type_="foreignkey")
    op.drop_column("notifications", "reminder_offset_days")
    op.drop_column("notifications", "reminder_due_date")
    op.drop_column("notifications", "payable_id")
    op.drop_column("notifications", "channel")

    op.drop_index("ix_reminder_preferences_user_id", table_name="reminder_preferences")
    op.drop_table("reminder_preferences")
    op.drop_index("ix_payables_owner_status_due", table_name="payables")
    op.drop_index("ix_payables_owner_due_date", table_name="payables")
    op.drop_index("ix_payables_status", table_name="payables")
    op.drop_index("ix_payables_due_date", table_name="payables")
    op.drop_index("ix_payables_analysis_id", table_name="payables")
    op.drop_index("ix_payables_owner_id", table_name="payables")
    op.drop_table("payables")
