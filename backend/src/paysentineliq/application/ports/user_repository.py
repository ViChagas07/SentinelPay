from typing import Protocol
from uuid import UUID

from paysentineliq.domain.user import User


class UserRepository(Protocol):
    async def get_by_google_sub(self, google_sub: str) -> User | None: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def create(
        self,
        *,
        google_sub: str,
        email: str,
        name: str | None,
    ) -> User: ...

    async def update_profile(
        self,
        user_id: UUID,
        *,
        email: str,
        name: str | None,
    ) -> User | None: ...
