from datetime import datetime
from typing import Protocol
from uuid import UUID

from paysentineliq.domain.refresh_token import RefreshTokenRecord


class RefreshTokenRepository(Protocol):
    async def add(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        family_id: UUID,
        expires_at: datetime,
    ) -> None: ...

    async def get_for_update(self, token_hash: str) -> RefreshTokenRecord | None: ...

    async def revoke(self, token_id: UUID, revoked_at: datetime) -> None: ...

    async def revoke_family(self, family_id: UUID, revoked_at: datetime) -> None: ...

    async def revoke_all_for_user(self, user_id: UUID, revoked_at: datetime) -> None: ...
