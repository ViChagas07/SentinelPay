"""notification type rollback compatibility

Revision ID: 0009_notification_rollback
Revises: 0008_notifications
Create Date: 2026-11-14 00:00:00.000000

The previous payables downgrade recreates a check constraint that only accepts
`analysis_completed`. Normalize notification types before that point so a
rollback does not fail when reminder/overdue rows exist.

"""

from alembic import op

revision = "0009_notification_rollback"
down_revision = "0008_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    op.execute(
        """
        UPDATE notifications
        SET type = 'analysis_completed'
        WHERE type <> 'analysis_completed'
        """,
    )
