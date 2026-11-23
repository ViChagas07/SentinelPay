from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from paysentineliq.application.commands.auth import AuthRequestContext, AuthService
from paysentineliq.application.errors import (
    AccountNotVerifiedError,
    InvalidAuthTokenError,
    InvalidCredentialsError,
    PasswordPolicyError,
    TooManyAttemptsError,
)
from paysentineliq.application.notifications.auth_emails import AuthEmail
from paysentineliq.application.security.account_lockout import lockout_delay_seconds
from paysentineliq.domain.auth_token import AuthTokenType
from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService
from paysentineliq.infrastructure.security.passwords import Argon2PasswordHasher
from tests.support.auth_fakes import (
    FakeRevokedTokenStore,
    FakeUnitOfWork,
    MutableClock,
)

pytestmark = pytest.mark.unit

_FAST = {
    "time_cost": 1,
    "memory_cost_kib": 8192,
    "parallelism": 1,
    "hash_len": 16,
    "salt_len": 8,
}
_CONTEXT = AuthRequestContext(ip="203.0.113.10", user_agent="pytest", locale="pt-BR")
_EMAIL = "pessoa@example.com"
_PASSWORD = "frase secreta longa"
_BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


class RecordingHasher(Argon2PasswordHasher):
    def __init__(self) -> None:
        super().__init__(**_FAST)
        self.dummy_calls = 0

    def verify_dummy(self, password: str) -> None:
        self.dummy_calls += 1
        super().verify_dummy(password)


def _service(
    *,
    hasher: RecordingHasher | None = None,
    base_url: str = "https://app.example",
    **overrides: object,
) -> tuple[AuthService, FakeUnitOfWork, RecordingHasher, MutableClock, JwtAccessTokenService]:
    uow = FakeUnitOfWork()
    clock = MutableClock(_BASE_TIME)
    tokens = JwtAccessTokenService(secret="s" * 64, ttl_minutes=15, clock=clock)
    resolved_hasher = hasher or RecordingHasher()
    service = AuthService(
        uow,
        tokens,
        FakeRevokedTokenStore(),
        refresh_ttl_days=7,
        clock=clock,
        password_hasher=resolved_hasher,
        public_base_url=base_url,
        **overrides,  # type: ignore[arg-type]
    )
    return service, uow, resolved_hasher, clock, tokens


def _password_user(uow: FakeUnitOfWork, *, verified: bool = True) -> User:
    user = User(
        id=uuid4(),
        google_sub=None,
        email=_EMAIL,
        name="Pessoa Exemplo",
        preferred_locale="pt-BR",
        timezone="America/Sao_Paulo",
        role=Role.USER,
        password_hash=RecordingHasher().hash(_PASSWORD),
        email_verified_at=_BASE_TIME if verified else None,
    )
    uow.users.users[user.id] = user
    return user


def _token_from_email(email: AuthEmail) -> str:
    marker = "token="
    start = email.text_body.index(marker) + len(marker)
    return email.text_body[start:].splitlines()[0].strip()


async def test_register_creates_unverified_user_with_hashed_password() -> None:
    service, uow, _, _, _ = _service()

    email = await service.register(
        name="Pessoa Exemplo",
        email="  Pessoa@Example.com ",
        password=_PASSWORD,
        context=_CONTEXT,
    )

    assert email is not None
    assert email.kind == "verify_email"
    stored = next(iter(uow.users.users.values()))
    assert stored.email == _EMAIL
    assert stored.email_verified_at is None
    assert stored.password_hash is not None
    assert _PASSWORD not in stored.password_hash
    assert len(uow.legal_consents.entries) == 2
    assert {entry.document.value for entry in uow.legal_consents.entries} == {
        "terms",
        "privacy",
    }
    assert "https://app.example/verificar-email?token=" in email.text_body
    assert "register" in uow.auth_events.types()


async def test_register_never_leaks_password_or_token_in_events() -> None:
    service, uow, _, _, _ = _service()

    email = await service.register(
        name="Pessoa Exemplo",
        email=_EMAIL,
        password=_PASSWORD,
        context=_CONTEXT,
    )

    assert email is not None
    token = _token_from_email(email)
    record = uow.auth_tokens.latest(AuthTokenType.EMAIL_VERIFICATION)
    assert record is not None
    serialized = repr([(event.event_type, event.metadata) for event in uow.auth_events.events])
    assert _PASSWORD not in serialized
    assert token not in serialized
    assert record.token_hash not in serialized


async def test_register_with_existing_email_sends_notice_without_duplicate() -> None:
    service, uow, _, _, _ = _service()
    existing = _password_user(uow)
    original_hash = existing.password_hash

    email = await service.register(
        name="Outra Pessoa",
        email=_EMAIL,
        password=_PASSWORD,
        context=_CONTEXT,
    )

    assert email is not None
    assert email.kind == "email_already_registered"
    assert len(uow.users.users) == 1
    assert uow.users.users[existing.id].password_hash == original_hash
    assert "register_duplicate" in uow.auth_events.types()


async def test_register_enforces_password_policy_before_writing() -> None:
    service, uow, _, _, _ = _service()

    with pytest.raises(PasswordPolicyError):
        await service.register(
            name="Pessoa Exemplo",
            email=_EMAIL,
            password="1234567890",
            context=_CONTEXT,
        )

    assert uow.users.users == {}


async def test_login_succeeds_and_resets_failures() -> None:
    service, uow, _, _, tokens = _service()
    user = _password_user(uow)
    uow.users.users[user.id] = replace(user, failed_login_count=3)

    result = await service.login(email=_EMAIL, password=_PASSWORD, context=_CONTEXT)

    assert result.user.id == user.id
    assert uow.users.users[user.id].failed_login_count == 0
    assert result.refresh_token
    claims = tokens.decode(result.access_token)
    assert claims.sub == user.id
    assert "login" in uow.auth_events.types()


async def test_login_with_wrong_password_is_generic_and_counts_failure() -> None:
    service, uow, _, _, _ = _service()
    user = _password_user(uow)

    with pytest.raises(InvalidCredentialsError) as error:
        await service.login(email=_EMAIL, password="senha errada longa", context=_CONTEXT)

    assert error.value.code == "invalid_credentials"
    assert uow.users.users[user.id].failed_login_count == 1
    assert "login_failed" in uow.auth_events.types()


async def test_login_with_unknown_email_runs_dummy_hash() -> None:
    service, uow, hasher, _, _ = _service()

    with pytest.raises(InvalidCredentialsError):
        await service.login(email="ninguem@example.com", password=_PASSWORD, context=_CONTEXT)

    assert hasher.dummy_calls == 1
    assert uow.users.users == {}


async def test_login_on_google_only_account_is_generic_and_runs_dummy_hash() -> None:
    service, uow, hasher, _, _ = _service()
    user = User(
        id=uuid4(),
        google_sub="google-1",
        email=_EMAIL,
        name="Pessoa",
        preferred_locale="pt-BR",
        timezone="America/Sao_Paulo",
        role=Role.USER,
    )
    uow.users.users[user.id] = user

    with pytest.raises(InvalidCredentialsError):
        await service.login(email=_EMAIL, password=_PASSWORD, context=_CONTEXT)

    assert hasher.dummy_calls == 1


async def test_login_blocks_progressively_and_hides_state_without_password() -> None:
    service, uow, _, clock, _ = _service()
    user = _password_user(uow)

    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            await service.login(
                email=_EMAIL,
                password="senha errada longa",
                context=_CONTEXT,
            )

    with pytest.raises(TooManyAttemptsError):
        await service.login(email=_EMAIL, password=_PASSWORD, context=_CONTEXT)

    with pytest.raises(InvalidCredentialsError):
        await service.login(email=_EMAIL, password="senha errada longa", context=_CONTEXT)

    clock.advance(seconds=31)
    result = await service.login(email=_EMAIL, password=_PASSWORD, context=_CONTEXT)
    assert result.user.id == user.id


async def test_login_with_unverified_email_requires_verification() -> None:
    service, uow, _, _, _ = _service()
    _password_user(uow, verified=False)

    with pytest.raises(AccountNotVerifiedError):
        await service.login(email=_EMAIL, password=_PASSWORD, context=_CONTEXT)

    assert "login_unverified" in uow.auth_events.types()


async def test_verify_email_consumes_token_once() -> None:
    service, uow, _, _, _ = _service()
    email = await service.register(
        name="Pessoa Exemplo",
        email=_EMAIL,
        password=_PASSWORD,
        context=_CONTEXT,
    )
    assert email is not None
    raw_token = _token_from_email(email)

    await service.verify_email(token=raw_token, context=_CONTEXT)

    stored = next(iter(uow.users.users.values()))
    assert stored.email_verified_at is not None
    assert "email_verified" in uow.auth_events.types()

    with pytest.raises(InvalidAuthTokenError):
        await service.verify_email(token=raw_token, context=_CONTEXT)


async def test_verify_email_rejects_expired_token() -> None:
    service, _, _, clock, _ = _service()
    email = await service.register(
        name="Pessoa Exemplo",
        email=_EMAIL,
        password=_PASSWORD,
        context=_CONTEXT,
    )
    assert email is not None
    raw_token = _token_from_email(email)
    clock.advance(days=2)

    with pytest.raises(InvalidAuthTokenError):
        await service.verify_email(token=raw_token, context=_CONTEXT)


async def test_verify_email_rejects_tampered_token() -> None:
    service, _, _, _, _ = _service()
    await service.register(
        name="Pessoa Exemplo",
        email=_EMAIL,
        password=_PASSWORD,
        context=_CONTEXT,
    )

    with pytest.raises(InvalidAuthTokenError):
        await service.verify_email(token="token-que-nao-existe", context=_CONTEXT)


async def test_resend_verification_rotates_token_and_is_neutral_for_unknown() -> None:
    service, uow, _, _, _ = _service()
    await service.register(
        name="Pessoa Exemplo",
        email=_EMAIL,
        password=_PASSWORD,
        context=_CONTEXT,
    )
    first = uow.auth_tokens.latest(AuthTokenType.EMAIL_VERIFICATION)
    assert first is not None

    email = await service.resend_verification(email=_EMAIL, context=_CONTEXT)

    assert email is not None
    second = uow.auth_tokens.latest(AuthTokenType.EMAIL_VERIFICATION)
    assert second is not None
    assert second.token_hash != first.token_hash
    assert uow.auth_tokens.records[first.token_hash].used_at is not None

    unknown = await service.resend_verification(
        email="ninguem@example.com",
        context=_CONTEXT,
    )
    assert unknown is None


async def test_forgot_password_is_neutral_and_sends_reset_link() -> None:
    service, uow, _, _, _ = _service()
    _password_user(uow)

    email = await service.forgot_password(email=_EMAIL, context=_CONTEXT)
    unknown = await service.forgot_password(email="ninguem@example.com", context=_CONTEXT)

    assert email is not None
    assert email.kind == "password_reset"
    assert "https://app.example/redefinir-senha?token=" in email.text_body
    assert unknown is None
    assert "password_reset_requested" in uow.auth_events.types()


async def test_forgot_password_for_google_account_explains_google() -> None:
    service, uow, _, _, _ = _service()
    user = User(
        id=uuid4(),
        google_sub="google-1",
        email=_EMAIL,
        name="Pessoa",
        preferred_locale="pt-BR",
        timezone="America/Sao_Paulo",
        role=Role.USER,
    )
    uow.users.users[user.id] = user

    email = await service.forgot_password(email=_EMAIL, context=_CONTEXT)

    assert email is not None
    assert email.kind == "google_account_reset"
    assert uow.auth_tokens.latest(AuthTokenType.PASSWORD_RESET) is None


async def test_reset_password_updates_hash_and_revokes_sessions() -> None:
    service, uow, hasher, _, _ = _service()
    user = _password_user(uow)
    login = await service.login(email=_EMAIL, password=_PASSWORD, context=_CONTEXT)
    email = await service.forgot_password(email=_EMAIL, context=_CONTEXT)
    assert email is not None
    raw_token = _token_from_email(email)

    await service.reset_password(
        token=raw_token,
        new_password="nova frase bem longa",
        context=_CONTEXT,
    )

    updated = uow.users.users[user.id]
    assert updated.password_hash is not None
    assert hasher.verify(updated.password_hash, "nova frase bem longa")
    assert updated.password_changed_at is not None
    assert all(record.revoked_at is not None for record in uow.refresh_tokens.records.values())
    assert login.refresh_token
    assert "password_reset_completed" in uow.auth_events.types()

    with pytest.raises(InvalidAuthTokenError):
        await service.reset_password(
            token=raw_token,
            new_password="outra frase bem longa",
            context=_CONTEXT,
        )


async def test_reset_password_rejects_expired_token() -> None:
    service, uow, _, clock, _ = _service()
    _password_user(uow)
    email = await service.forgot_password(email=_EMAIL, context=_CONTEXT)
    assert email is not None
    raw_token = _token_from_email(email)
    clock.advance(minutes=31)

    with pytest.raises(InvalidAuthTokenError):
        await service.reset_password(
            token=raw_token,
            new_password="nova frase bem longa",
            context=_CONTEXT,
        )


async def test_reset_password_enforces_policy() -> None:
    service, uow, _, _, _ = _service()
    _password_user(uow)
    email = await service.forgot_password(email=_EMAIL, context=_CONTEXT)
    assert email is not None
    raw_token = _token_from_email(email)

    with pytest.raises(PasswordPolicyError):
        await service.reset_password(
            token=raw_token,
            new_password="1234567890",
            context=_CONTEXT,
        )


async def test_change_password_requires_current_password() -> None:
    service, uow, _, _, _ = _service()
    user = _password_user(uow)

    with pytest.raises(InvalidCredentialsError):
        await service.change_password(
            user_id=user.id,
            current_password="senha errada longa",
            new_password="nova frase bem longa",
            context=_CONTEXT,
        )

    await service.change_password(
        user_id=user.id,
        current_password=_PASSWORD,
        new_password="nova frase bem longa",
        context=_CONTEXT,
    )

    assert "password_changed" in uow.auth_events.types()


async def test_password_flow_requires_configuration() -> None:
    service, _, _, _, _ = _service(base_url="")

    with pytest.raises(Exception) as error:
        await service.register(
            name="Pessoa",
            email=_EMAIL,
            password=_PASSWORD,
            context=_CONTEXT,
        )

    assert getattr(error.value, "code", "") == "auth_not_configured"


def test_lockout_delay_grows_and_is_capped() -> None:
    assert lockout_delay_seconds(1, max_attempts=5, base_seconds=30, max_seconds=3600) == 0
    assert lockout_delay_seconds(5, max_attempts=5, base_seconds=30, max_seconds=3600) == 30
    assert lockout_delay_seconds(6, max_attempts=5, base_seconds=30, max_seconds=3600) == 60
    assert lockout_delay_seconds(20, max_attempts=5, base_seconds=30, max_seconds=3600) == 3600
