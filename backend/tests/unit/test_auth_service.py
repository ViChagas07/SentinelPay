from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from paysentineliq.application.commands.auth import AuthService
from paysentineliq.application.errors import (
    InvalidRefreshTokenError,
    RefreshTokenReuseError,
)
from paysentineliq.application.ports.oidc import GoogleIdentity
from paysentineliq.application.security.refresh_tokens import hash_refresh_token
from paysentineliq.domain.user import Role
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService
from tests.support.auth_fakes import (
    FakeRevokedTokenStore,
    FakeUnitOfWork,
    MutableClock,
)

pytestmark = pytest.mark.unit

_BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)
_IDENTITY = GoogleIdentity(
    google_sub="google-sub-1",
    email="user@example.com",
    name="User",
)


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
    assert result.user.email_verified_at is not None

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


async def test_google_first_access_records_consents_and_event() -> None:
    service, uow, _, _, _ = _service()

    await service.login_with_google(_IDENTITY)

    documents = sorted(entry.document.value for entry in uow.legal_consents.entries)
    assert documents == ["privacy", "terms"]
    assert all(entry.version == "1.1" for entry in uow.legal_consents.entries)
    assert uow.auth_events.types() == ["google_signup"]


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
    assert "logout" in uow.auth_events.types()


async def test_google_new_sub_with_unverified_local_email_is_blocked() -> None:
    service, uow, _, _, _ = _service()
    existing = await uow.users.create_password_user(
        email="user@example.com",
        name="User",
        password_hash="$argon2id$placeholder",
    )
    assert existing.email_verified_at is None
    uow.auth_events.events.clear()

    from paysentineliq.application.errors import OAuthAuthenticationError

    with pytest.raises(OAuthAuthenticationError):
        await service.login_with_google(_IDENTITY)

    stored = uow.users.users[existing.id]
    assert stored.google_sub is None
    assert "google_link_blocked" in uow.auth_events.types()


async def test_google_links_verified_password_account() -> None:
    service, uow, _, _, _ = _service()
    verified_at = datetime(2026, 1, 1, tzinfo=UTC)
    user = await uow.users.create_password_user(
        email="user@example.com",
        name="User",
        password_hash="$argon2id$placeholder",
    )
    await uow.users.mark_email_verified(user.id, verified_at=verified_at)
    uow.auth_events.events.clear()

    result = await service.login_with_google(_IDENTITY)

    assert result.user.id == user.id
    assert result.user.google_sub == _IDENTITY.google_sub
    assert "google_linked" in uow.auth_events.types()
    assert len(uow.users.users) == 1
