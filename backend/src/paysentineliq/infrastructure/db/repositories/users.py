from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.db.models import UserModel


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        model = await self._session.scalar(
            select(UserModel).where(UserModel.google_sub == google_sub)
        )
        return _to_domain(model) if model is not None else None

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return _to_domain(model) if model is not None else None

    async def create(
        self,
        *,
        google_sub: str,
        email: str,
        name: str | None,
    ) -> User:
        model = UserModel(
            google_sub=google_sub,
            email=email,
            name=name,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def update_profile(
        self,
        user_id: UUID,
        *,
        email: str,
        name: str | None,
    ) -> User | None:
        model = await self._session.get(UserModel, user_id)
        if model is None:
            return None
        model.email = email
        model.name = name
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        google_sub=model.google_sub,
        email=model.email,
        name=model.name,
        preferred_locale=model.preferred_locale,
        timezone=model.timezone,
        role=Role(model.role),
    )
