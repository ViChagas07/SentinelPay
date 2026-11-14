"""notification center, preferences and deliveries

Revision ID: 0008_notifications
Revises: 0007_payables
Create Date: 2026-11-14 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0008_notifications"
down_revision = "0007_payables"
branch_labels = None
depends_on = None

_NEW_TYPES = (
    "'analysis_completed', 'high_risk_detected', 'receipt_analyzed', "
    "'payable_due_soon', 'payable_due_today', 'payable_overdue', "
    "'payable_due_reminder'"
)
_OLD_TYPES = "'analysis_completed', 'payable_due_reminder'"


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_notifications_owner_read_at",
        "notifications",
        ["owner_id", "read_at"],
        unique=False,
    )
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type",
        "notifications",
        f"type IN ({_NEW_TYPES})",
    )
    op.create_index(
        "uq_notifications_payable_overdue",
        "notifications",
        ["payable_id"],
        unique=True,
        postgresql_where=sa.text("type = 'payable_overdue'"),
    )

    op.create_table(
        "notification_preferences",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("destination_encrypted", sa.Text(), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
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
            "channel IN ('email', 'sms', 'whatsapp')",
            name="ck_notification_preferences_channel",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "channel",
            name="uq_notification_preferences_user_channel",
        ),
    )
    op.create_index(
        "ix_notification_preferences_user_id",
        "notification_preferences",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "notification_deliveries",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("last_error_safe", sa.String(length=200), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
            "channel IN ('email', 'sms', 'whatsapp')",
            name="ck_notification_deliveries_channel",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'skipped')",
            name="ck_notification_deliveries_status",
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notifications.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_id",
            "channel",
            name="uq_notification_deliveries_notification_channel",
        ),
    )
    op.create_index(
        "ix_notification_deliveries_notification_id",
        "notification_deliveries",
        ["notification_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_deliveries_status",
        "notification_deliveries",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_deliveries_status",
        table_name="notification_deliveries",
    )
    op.drop_index(
        "ix_notification_deliveries_notification_id",
        table_name="notification_deliveries",
    )
    op.drop_table("notification_deliveries")

    op.drop_index(
        "ix_notification_preferences_user_id",
        table_name="notification_preferences",
    )
    op.drop_table("notification_preferences")

    op.drop_index("uq_notifications_payable_overdue", table_name="notifications")
    op.execute(
        """
        UPDATE notifications
        SET type = CASE
            WHEN type IN ('payable_due_soon', 'payable_due_today', 'payable_overdue')
                THEN 'payable_due_reminder'
            ELSE 'analysis_completed'
        END
        WHERE type NOT IN ('analysis_completed', 'payable_due_reminder')
        """,
    )
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type",
        "notifications",
        f"type IN ({_OLD_TYPES})",
    )
    op.drop_index("ix_notifications_owner_read_at", table_name="notifications")
    op.drop_column("notifications", "read_at")
