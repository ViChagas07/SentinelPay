from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class AuthTokenType(StrEnum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


@dataclass(frozen=True, slots=True)
class AuthToken:
    id: UUID
    user_id: UUID
    token_type: AuthTokenType
    token_hash: str
    expires_at: datetime
    used_at: datetime | None
    created_ip: str | None
    created_user_agent: str | None
