from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
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
            "type IN ('analysis_completed')",
            name="ck_notifications_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'dispatched', 'failed')",
            name="ck_notifications_status",
        ),
        Index("ix_notifications_owner_created_at", "owner_id", "created_at"),
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
