from types import TracebackType
from typing import Protocol, Self

from paysentineliq.application.ports.refresh_token_repository import (
    RefreshTokenRepository,
)
from paysentineliq.application.ports.user_repository import UserRepository


class AuthUnitOfWork(Protocol):
    @property
    def users(self) -> UserRepository: ...

    @property
    def refresh_tokens(self) -> RefreshTokenRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
