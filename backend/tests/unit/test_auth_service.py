from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from paysentineliq.application.commands.auth import AuthService
from paysentineliq.application.errors import (
    InvalidRefreshTokenError,
    RefreshTokenReuseError,
)
from paysentineliq.application.ports.oidc import GoogleIdentity
from paysentineliq.application.security.refresh_tokens import hash_refresh_token
from paysentineliq.domain.refresh_token import RefreshTokenRecord
from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService

pytestmark = pytest.mark.unit

_BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)
_IDENTITY = GoogleIdentity(
    google_sub="google-sub-1",
    email="user@example.com",
    name="User",
)


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        return next(
            (user for user in self.users.values() if user.google_sub == google_sub),
            None,
        )

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def create(
        self,
        *,
        google_sub: str,
        email: str,
        name: str | None,
    ) -> User:
        user = User(
            id=uuid4(),
            google_sub=google_sub,
            email=email,
            name=name,
            preferred_locale="pt-BR",
            timezone="America/Sao_Paulo",
            role=Role.USER,
        )
        self.users[user.id] = user
        return user

    async def update_profile(
        self,
        user_id: UUID,
        *,
        email: str,
        name: str | None,
    ) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        updated = replace(user, email=email, name=name)
        self.users[user_id] = updated
        return updated


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self.records: dict[str, RefreshTokenRecord] = {}

    async def add(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        family_id: UUID,
        expires_at: datetime,
    ) -> None:
        self.records[token_hash] = RefreshTokenRecord(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            family_id=family_id,
            expires_at=expires_at,
            revoked_at=None,
        )

    async def get_for_update(self, token_hash: str) -> RefreshTokenRecord | None:
        return self.records.get(token_hash)

    async def revoke(self, token_id: UUID, revoked_at: datetime) -> None:
        for token_hash, record in list(self.records.items()):
            if record.id == token_id:
                self.records[token_hash] = replace(
                    record,
                    revoked_at=revoked_at,
                )

    async def revoke_family(self, family_id: UUID, revoked_at: datetime) -> None:
        for token_hash, record in list(self.records.items()):
            if record.family_id == family_id and record.revoked_at is None:
                self.records[token_hash] = replace(
                    record,
                    revoked_at=revoked_at,
                )


class FakeRevokedTokenStore:
    def __init__(self) -> None:
        self.revoked: dict[str, int] = {}

    async def revoke(self, jti: str, expires_at: int) -> None:
        self.revoked[jti] = expires_at

    async def is_revoked(self, jti: str) -> bool:
        return jti in self.revoked


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.users = FakeUserRepository()
        self.refresh_tokens = FakeRefreshTokenRepository()
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _service() -> tuple[
    AuthService,
    FakeUnitOfWork,
    JwtAccessTokenService,
    FakeRevokedTokenStore,
    MutableClock,
]:
    uow = FakeUnitOfWork()
    clock = MutableClock(_BASE_TIME)
    token_service = JwtAccessTokenService(
        secret="s" * 64,
        ttl_minutes=15,
        clock=clock,
    )
    revoked = FakeRevokedTokenStore()
    service = AuthService(
        uow,
        token_service,
        revoked,
        refresh_ttl_days=7,
        clock=clock,
    )
    return service, uow, token_service, revoked, clock


async def test_login_creates_user_and_stores_only_refresh_hash() -> None:
    service, uow, token_service, _, _ = _service()

    result = await service.login_with_google(_IDENTITY)

    assert result.user.google_sub == _IDENTITY.google_sub
    assert result.user.role is Role.USER
    assert result.user.preferred_locale == "pt-BR"
    assert result.user.timezone == "America/Sao_Paulo"

    claims = token_service.decode(result.access_token)
    assert claims.sub == result.user.id
    assert claims.role is Role.USER

    records = list(uow.refresh_tokens.records.values())
    assert len(records) == 1
    assert records[0].token_hash == hash_refresh_token(result.refresh_token)
    assert result.refresh_token not in records[0].token_hash


async def test_login_updates_existing_profile_without_changing_role() -> None:
    service, uow, _, _, _ = _service()
    existing = await uow.users.create(
        google_sub=_IDENTITY.google_sub,
        email="old@example.com",
        name="Old",
    )
    admin = replace(existing, role=Role.ADMIN)
    uow.users.users[admin.id] = admin

    result = await service.login_with_google(
        GoogleIdentity(
            google_sub=_IDENTITY.google_sub,
            email="new@example.com",
            name="New",
        )
    )

    assert result.user.id == admin.id
    assert result.user.email == "new@example.com"
    assert result.user.role is Role.ADMIN


async def test_refresh_rotates_token_in_same_family() -> None:
    service, uow, token_service, _, clock = _service()
    login = await service.login_with_google(_IDENTITY)
    clock.value = _BASE_TIME + timedelta(minutes=1)

    refreshed = await service.refresh(login.refresh_token)

    assert refreshed.refresh_token != login.refresh_token
    assert refreshed.refresh_expires_at > login.refresh_expires_at

    old_record = uow.refresh_tokens.records[hash_refresh_token(login.refresh_token)]
    new_record = uow.refresh_tokens.records[hash_refresh_token(refreshed.refresh_token)]
    assert old_record.revoked_at is not None
    assert new_record.revoked_at is None
    assert old_record.family_id == new_record.family_id

    claims = token_service.decode(refreshed.access_token)
    assert claims.sub == login.user.id


async def test_expired_refresh_is_rejected() -> None:
    service, _, _, _, clock = _service()
    login = await service.login_with_google(_IDENTITY)
    clock.value = _BASE_TIME + timedelta(days=8)

    with pytest.raises(InvalidRefreshTokenError):
        await service.refresh(login.refresh_token)


async def test_refresh_reuse_revokes_entire_family() -> None:
    service, uow, _, _, _ = _service()
    login = await service.login_with_google(_IDENTITY)
    refreshed = await service.refresh(login.refresh_token)

    with pytest.raises(RefreshTokenReuseError):
        await service.refresh(login.refresh_token)

    records = list(uow.refresh_tokens.records.values())
    assert all(record.revoked_at is not None for record in records)
    assert (
        uow.refresh_tokens.records[hash_refresh_token(refreshed.refresh_token)].revoked_at
        is not None
    )


async def test_logout_revokes_family_and_jti() -> None:
    service, uow, token_service, revoked, _ = _service()
    login = await service.login_with_google(_IDENTITY)
    claims = token_service.decode(login.access_token)

    await service.logout(login.refresh_token, claims)

    records = list(uow.refresh_tokens.records.values())
    assert all(record.revoked_at is not None for record in records)
    assert revoked.revoked[claims.jti] == claims.exp
