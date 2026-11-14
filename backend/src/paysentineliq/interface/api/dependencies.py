from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from paysentineliq.application.locale import resolve_locale
from paysentineliq.application.ports.auth_unit_of_work import AuthUnitOfWork
from paysentineliq.application.ports.readiness import ReadinessChecker
from paysentineliq.application.ports.unit_of_work import UnitOfWork
from paysentineliq.application.use_cases.example import ExampleService
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork
from paysentineliq.infrastructure.readiness import SqlAlchemyRedisReadinessChecker


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


def get_unit_of_work(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(session)


def get_auth_unit_of_work(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthUnitOfWork:
    return SqlAlchemyUnitOfWork(session)


def get_example_service(
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ExampleService:
    return ExampleService(uow)


def get_readiness_checker(request: Request) -> ReadinessChecker:
    engine: AsyncEngine = request.app.state.engine
    redis: Redis = request.app.state.redis
    return SqlAlchemyRedisReadinessChecker(engine, redis)


def get_locale(
    accept_language: Annotated[str | None, Header(alias="Accept-Language")] = None,
) -> str:
    return resolve_locale(accept_language)
