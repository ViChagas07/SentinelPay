from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    google_sub: str
    email: str
    name: str | None
    preferred_locale: str
    timezone: str
    role: Role
