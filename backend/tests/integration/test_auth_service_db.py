import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paysentineliq.application.commands.auth import AuthService
from paysentineliq.application.errors import RefreshTokenReuseError
from paysentineliq.application.ports.oidc import GoogleIdentity
from paysentineliq.domain.user import Role
from paysentineliq.infrastructure.db.models import RefreshTokenModel, UserModel
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class NoopRevokedStore:
    def __init__(self) -> None:
        self.revoked: set[str] = set()

    async def revoke(self, jti: str, expires_at: int) -> None:
        self.revoked.add(jti)

    async def is_revoked(self, jti: str) -> bool:
        return jti in self.revoked


async def test_refresh_rotation_and_reuse_against_postgres() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    user_id = None

    try:
        async with factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            token_service = JwtAccessTokenService(
                secret="s" * 64,
                ttl_minutes=15,
                clock=lambda: _NOW,
            )
            service = AuthService(
                uow,
                token_service,
                NoopRevokedStore(),
                refresh_ttl_days=7,
                clock=lambda: _NOW,
            )

            login = await service.login_with_google(
                GoogleIdentity(
                    google_sub=f"sub-{unique}",
                    email=f"{unique}@example.com",
                    name="DB User",
                )
            )
            user_id = login.user.id
            assert login.user.role is Role.USER

            refreshed = await service.refresh(login.refresh_token)
            assert refreshed.user.id == user_id

            with pytest.raises(RefreshTokenReuseError):
                await service.refresh(login.refresh_token)

            records = (
                await session.scalars(
                    select(RefreshTokenModel).where(RefreshTokenModel.user_id == user_id)
                )
            ).all()
            assert len(records) == 2
            assert all(record.revoked_at is not None for record in records)
    finally:
        async with factory() as session:
            if user_id is not None:
                await session.execute(
                    delete(RefreshTokenModel).where(RefreshTokenModel.user_id == user_id)
                )
                await session.execute(delete(UserModel).where(UserModel.id == user_id))
                await session.commit()
        await engine.dispose()
