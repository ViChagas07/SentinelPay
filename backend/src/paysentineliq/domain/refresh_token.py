from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RefreshTokenRecord:
    id: UUID
    user_id: UUID
    token_hash: str
    family_id: UUID
    expires_at: datetime
    revoked_at: datetime | None
