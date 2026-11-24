from typing import Protocol


class LoginTicketStore(Protocol):
    async def issue(self, refresh_token: str, ttl_seconds: int) -> str: ...

    async def consume(self, ticket: str) -> str | None: ...
