from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from paysentineliq.domain.auth_token import AuthToken, AuthTokenType
from paysentineliq.infrastructure.db.models import AuthTokenModel


class SqlAlchemyAuthTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        user_id: UUID,
        token_type: AuthTokenType,
        token_hash: str,
        expires_at: datetime,
        created_ip: str | None,
        created_user_agent: str | None,
    ) -> AuthToken:
        model = AuthTokenModel(
            user_id=user_id,
            token_type=token_type.value,
            token_hash=token_hash,
            expires_at=expires_at,
            created_ip=created_ip,
            created_user_agent=created_user_agent,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def get_by_hash(self, token_hash: str) -> AuthToken | None:
        model = await self._session.scalar(
            select(AuthTokenModel).where(AuthTokenModel.token_hash == token_hash).with_for_update()
        )
        return _to_domain(model) if model is not None else None

    async def mark_used(self, token_id: UUID, *, used_at: datetime) -> None:
        await self._session.execute(
            update(AuthTokenModel).where(AuthTokenModel.id == token_id).values(used_at=used_at)
        )
        await self._session.flush()

    async def invalidate_unused(
        self,
        *,
        user_id: UUID,
        token_type: AuthTokenType,
        used_at: datetime,
    ) -> None:
        await self._session.execute(
            update(AuthTokenModel)
            .where(
                AuthTokenModel.user_id == user_id,
                AuthTokenModel.token_type == token_type.value,
                AuthTokenModel.used_at.is_(None),
            )
            .values(used_at=used_at)
        )
        await self._session.flush()


def _to_domain(model: AuthTokenModel) -> AuthToken:
    return AuthToken(
        id=model.id,
        user_id=model.user_id,
        token_type=AuthTokenType(model.token_type),
        token_hash=model.token_hash,
        expires_at=model.expires_at,
        used_at=model.used_at,
        created_ip=model.created_ip,
        created_user_agent=model.created_user_agent,
    )
