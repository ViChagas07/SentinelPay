from typing import Protocol

from paysentineliq.domain.auth_event import AuthEvent


class AuthEventRepository(Protocol):
    async def add(self, event: AuthEvent) -> None: ...
