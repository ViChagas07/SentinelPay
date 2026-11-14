from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from paysentineliq.application.ports.refresh_token_repository import (
    RefreshTokenRepository,
)
from paysentineliq.application.ports.repository import ExampleRepository
from paysentineliq.application.ports.user_repository import UserRepository
from paysentineliq.infrastructure.db.repositories.example import (
    SqlAlchemyExampleRepository,
)
from paysentineliq.infrastructure.db.repositories.refresh_tokens import (
    SqlAlchemyRefreshTokenRepository,
)
from paysentineliq.infrastructure.db.repositories.users import (
    SqlAlchemyUserRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.examples: ExampleRepository = SqlAlchemyExampleRepository(session)
        self.users: UserRepository = SqlAlchemyUserRepository(session)
        self.refresh_tokens: RefreshTokenRepository = SqlAlchemyRefreshTokenRepository(session)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
