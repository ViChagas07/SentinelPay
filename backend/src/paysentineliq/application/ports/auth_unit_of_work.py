from typing import Protocol

from paysentineliq.application.ports.refresh_token_repository import (
    RefreshTokenRepository,
)
from paysentineliq.application.ports.unit_of_work import UnitOfWork
from paysentineliq.application.ports.user_repository import UserRepository


class AuthUnitOfWork(UnitOfWork, Protocol):
    @property
    def users(self) -> UserRepository: ...

    @property
    def refresh_tokens(self) -> RefreshTokenRepository: ...
