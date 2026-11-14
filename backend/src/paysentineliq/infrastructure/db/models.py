from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

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
