from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from paysentineliq.application.errors import EmailAlreadyExistsError
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

    async def get_by_email(self, email: str) -> User | None:
        model = await self._session.scalar(
            select(UserModel).where(func.lower(UserModel.email) == email.strip().lower())
        )
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

    async def create_password_user(
        self,
        *,
        email: str,
        name: str,
        password_hash: str,
    ) -> User:
        model = UserModel(
            google_sub=None,
            email=email,
            name=name,
            password_hash=password_hash,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise EmailAlreadyExistsError() from exc
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

    async def set_password_hash(
        self,
        user_id: UUID,
        *,
        password_hash: str,
        changed_at: datetime,
    ) -> None:
        model = await self._session.get(UserModel, user_id)
        if model is None:
            return
        model.password_hash = password_hash
        model.password_changed_at = changed_at
        await self._session.flush()

    async def mark_email_verified(self, user_id: UUID, *, verified_at: datetime) -> None:
        model = await self._session.get(UserModel, user_id)
        if model is None:
            return
        model.email_verified_at = verified_at
        await self._session.flush()

    async def record_login_failure(
        self,
        user_id: UUID,
        *,
        failed_login_count: int,
        locked_until: datetime | None,
    ) -> None:
        model = await self._session.get(UserModel, user_id)
        if model is None:
            return
        model.failed_login_count = failed_login_count
        model.locked_until = locked_until
        await self._session.flush()

    async def reset_login_failures(self, user_id: UUID) -> None:
        model = await self._session.get(UserModel, user_id)
        if model is None:
            return
        model.failed_login_count = 0
        model.locked_until = None
        await self._session.flush()

    async def link_google_sub(self, user_id: UUID, *, google_sub: str) -> None:
        model = await self._session.get(UserModel, user_id)
        if model is None:
            return
        model.google_sub = google_sub
        await self._session.flush()


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        google_sub=model.google_sub,
        email=model.email,
        name=model.name,
        preferred_locale=model.preferred_locale,
        timezone=model.timezone,
        role=Role(model.role),
        password_hash=model.password_hash,
        email_verified_at=model.email_verified_at,
        password_changed_at=model.password_changed_at,
        failed_login_count=model.failed_login_count,
        locked_until=model.locked_until,
    )
