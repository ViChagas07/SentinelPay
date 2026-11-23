from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    google_sub: str | None
    email: str
    name: str | None
    preferred_locale: str
    timezone: str
    role: Role
    password_hash: str | None = None
    email_verified_at: datetime | None = None
    password_changed_at: datetime | None = None
    failed_login_count: int = 0
    locked_until: datetime | None = None
