from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from paysentineliq.domain.refresh_token import RefreshTokenRecord
from paysentineliq.infrastructure.db.models import RefreshTokenModel


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        family_id: UUID,
        expires_at: datetime,
    ) -> None:
        self._session.add(
            RefreshTokenModel(
                user_id=user_id,
                token_hash=token_hash,
                family_id=family_id,
                expires_at=expires_at,
            )
        )
        await self._session.flush()

    async def get_for_update(self, token_hash: str) -> RefreshTokenRecord | None:
        model = await self._session.scalar(
            select(RefreshTokenModel)
            .where(RefreshTokenModel.token_hash == token_hash)
            .with_for_update()
        )
        return _to_domain(model) if model is not None else None

    async def revoke(self, token_id: UUID, revoked_at: datetime) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.id == token_id)
            .values(revoked_at=revoked_at)
        )

    async def revoke_family(self, family_id: UUID, revoked_at: datetime) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.family_id == family_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )


def _to_domain(model: RefreshTokenModel) -> RefreshTokenRecord:
    return RefreshTokenRecord(
        id=model.id,
        user_id=model.user_id,
        token_hash=model.token_hash,
        family_id=model.family_id,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
    )
