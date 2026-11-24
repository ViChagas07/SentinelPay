import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paysentineliq.domain.user import Role
from paysentineliq.infrastructure.db.models import RefreshTokenModel, UserModel
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_user_and_refresh_repository_roundtrip() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    user_id: UUID | None = None

    try:
        async with factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            async with uow:
                user = await uow.users.create(
                    google_sub=f"sub-{unique}",
                    email=f"{unique}@example.com",
                    name="Test User",
                )
                user_id = user.id

                assert user.role is Role.USER
                assert user.preferred_locale == "pt-BR"
                assert user.timezone == "America/Sao_Paulo"

                assert user.google_sub is not None
                fetched = await uow.users.get_by_google_sub(user.google_sub)
                assert fetched == user

                updated = await uow.users.update_profile(
                    user.id,
                    email=f"new-{unique}@example.com",
                    name="Updated User",
                )
                assert updated is not None
                assert updated.email == f"new-{unique}@example.com"
                assert updated.name == "Updated User"

                token_hash = hashlib.sha256(unique.encode()).hexdigest()
                family_id = uuid4()
                expires_at = datetime.now(UTC) + timedelta(days=1)
                await uow.refresh_tokens.add(
                    user_id=user.id,
                    token_hash=token_hash,
                    family_id=family_id,
                    expires_at=expires_at,
                )

                record = await uow.refresh_tokens.get_for_update(token_hash)
                assert record is not None
                assert record.family_id == family_id

                await uow.refresh_tokens.revoke(
                    record.id,
                    datetime.now(UTC),
                )
                revoked = await uow.refresh_tokens.get_for_update(token_hash)
                assert revoked is not None
                assert revoked.revoked_at is not None

                await uow.refresh_tokens.revoke_family(
                    family_id,
                    datetime.now(UTC),
                )
                await uow.commit()
    finally:
        async with factory() as session:
            if user_id is not None:
                await session.execute(
                    delete(RefreshTokenModel).where(RefreshTokenModel.user_id == user_id)
                )
                await session.execute(delete(UserModel).where(UserModel.id == user_id))
                await session.commit()
        await engine.dispose()
