from datetime import datetime
from typing import Protocol
from uuid import UUID

from paysentineliq.domain.auth_token import AuthToken, AuthTokenType


class AuthTokenRepository(Protocol):
    async def add(
        self,
        *,
        user_id: UUID,
        token_type: AuthTokenType,
        token_hash: str,
        expires_at: datetime,
        created_ip: str | None,
        created_user_agent: str | None,
    ) -> AuthToken: ...

    async def get_by_hash(self, token_hash: str) -> AuthToken | None: ...

    async def mark_used(self, token_id: UUID, *, used_at: datetime) -> None: ...

    async def invalidate_unused(
        self,
        *,
        user_id: UUID,
        token_type: AuthTokenType,
        used_at: datetime,
    ) -> None: ...
