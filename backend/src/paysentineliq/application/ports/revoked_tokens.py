from typing import Protocol


class RevokedTokenStore(Protocol):
    async def revoke(self, jti: str, expires_at: int) -> None: ...

    async def is_revoked(self, jti: str) -> bool: ...
