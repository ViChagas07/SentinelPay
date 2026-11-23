from datetime import datetime
from typing import Protocol
from uuid import UUID

from paysentineliq.domain.user import User


class UserRepository(Protocol):
    async def get_by_google_sub(self, google_sub: str) -> User | None: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def create(
        self,
        *,
        google_sub: str,
        email: str,
        name: str | None,
    ) -> User: ...

    async def create_password_user(
        self,
        *,
        email: str,
        name: str,
        password_hash: str,
    ) -> User: ...

    async def update_profile(
        self,
        user_id: UUID,
        *,
        email: str,
        name: str | None,
    ) -> User | None: ...

    async def set_password_hash(
        self,
        user_id: UUID,
        *,
        password_hash: str,
        changed_at: datetime,
    ) -> None: ...

    async def mark_email_verified(self, user_id: UUID, *, verified_at: datetime) -> None: ...

    async def record_login_failure(
        self,
        user_id: UUID,
        *,
        failed_login_count: int,
        locked_until: datetime | None,
    ) -> None: ...

    async def reset_login_failures(self, user_id: UUID) -> None: ...

    async def link_google_sub(self, user_id: UUID, *, google_sub: str) -> None: ...
