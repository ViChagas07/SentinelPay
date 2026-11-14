from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from paysentineliq.infrastructure.db.base import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),)

    google_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_locale: Mapped[str] = mapped_column(
        String(16),
        default="pt-BR",
        server_default="pt-BR",
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        default="America/Sao_Paulo",
        server_default="America/Sao_Paulo",
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(16),
        default="user",
        server_default="user",
        nullable=False,
    )


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    family_id: Mapped[UUID] = mapped_column(Uuid, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentModel(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('bank_slip', 'payslip', 'receipt')",
            name="ck_documents_kind",
        ),
    )

    owner_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(512), unique=True, index=True, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    original_name_sanitized: Mapped[str] = mapped_column(String(255), nullable=False)


class AnalysisModel(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_analyses_owner_idempotency",
        ),
        Index("ix_analyses_owner_created_at", "owner_id", "created_at"),
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'degraded')",
            name="ck_analyses_status",
        ),
    )

    owner_id: Mapped[UUID] = mapped_column(Uuid, index=True, nullable=False)
    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    band: Mapped[str | None] = mapped_column(String(16), nullable=True)
    rule_set_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_versions: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    degradation_flags: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    state: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    report_s3_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    events: Mapped[list["AnalysisEventModel"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
    )


class AnalysisEventModel(Base):
    __tablename__ = "analysis_events"

    analysis_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("analyses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    rule_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rule_set_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    degradation_flags: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    payload: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    analysis: Mapped[AnalysisModel] = relationship(back_populates="events")


class NotificationModel(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "type IN ('analysis_completed', 'high_risk_detected', 'receipt_analyzed', "
            "'payable_due_soon', 'payable_due_today', 'payable_overdue', "
            "'payable_due_reminder')",
            name="ck_notifications_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'dispatched', 'failed', 'cancelled')",
            name="ck_notifications_status",
        ),
        Index("ix_notifications_owner_created_at", "owner_id", "created_at"),
        Index("ix_notifications_owner_read_at", "owner_id", "read_at"),
        Index(
            "uq_notifications_payable_overdue",
            "payable_id",
            unique=True,
            postgresql_where=text("type = 'payable_overdue'"),
        ),
        UniqueConstraint(
            "payable_id",
            "reminder_due_date",
            "reminder_offset_days",
            "channel",
            name="uq_notifications_payable_reminder",
        ),
    )

    owner_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("analyses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default="pending",
        server_default="pending",
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(
        String(16),
        default="in_app",
        server_default="in_app",
        nullable=False,
    )
    payable_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("payables.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    reminder_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reminder_offset_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PayableModel(Base):
    __tablename__ = "payables"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_confirmation', 'pending', 'paid', 'overdue', 'dismissed')",
            name="ck_payables_status",
        ),
        UniqueConstraint("analysis_id", name="uq_payables_analysis_id"),
        Index("ix_payables_owner_due_date", "owner_id", "due_date"),
        Index("ix_payables_owner_status_due", "owner_id", "status", "due_date"),
    )

    owner_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("analyses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)


class ReminderPreferenceModel(Base):
    __tablename__ = "reminder_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_reminder_preferences_user_id"),)

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    offsets_days: Mapped[list[int]] = mapped_column(
        JSONB,
        default=lambda: [3, 1, 0],
        server_default=text("'[3, 1, 0]'::jsonb"),
        nullable=False,
    )
    local_time: Mapped[time] = mapped_column(
        Time(),
        default=lambda: time(9, 0),
        server_default="09:00:00",
        nullable=False,
    )
    channels: Mapped[list[str]] = mapped_column(
        JSONB,
        default=lambda: ["in_app"],
        server_default=text("'[\"in_app\"]'::jsonb"),
        nullable=False,
    )


class NotificationPreferenceModel(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "channel", name="uq_notification_preferences_user_channel"),
        CheckConstraint(
            "channel IN ('email', 'sms', 'whatsapp')",
            name="ck_notification_preferences_channel",
        ),
        Index("ix_notification_preferences_user_id", "user_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    destination_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class NotificationDeliveryModel(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "channel",
            name="uq_notification_deliveries_notification_channel",
        ),
        CheckConstraint(
            "channel IN ('email', 'sms', 'whatsapp')",
            name="ck_notification_deliveries_channel",
        ),
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'skipped')",
            name="ck_notification_deliveries_status",
        ),
        Index("ix_notification_deliveries_notification_id", "notification_id"),
        Index("ix_notification_deliveries_status", "status"),
    )

    notification_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        default="pending",
        server_default="pending",
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    last_error_safe: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
