from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from paysentineliq.application.commands.auth import AuthResult
from paysentineliq.application.errors import (
    AccountNotVerifiedError,
    InvalidAuthTokenError,
    InvalidCredentialsError,
    PasswordPolicyError,
    TooManyAttemptsError,
)
from paysentineliq.application.notifications.auth_emails import render_auth_email
from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.interface.api.dependencies import (
    get_auth_email_sender,
    get_auth_rate_limiter,
    get_auth_service,
)
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit

_BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)
_USER = User(
    id=uuid4(),
    google_sub=None,
    email="pessoa@example.com",
    name="Pessoa Exemplo",
    preferred_locale="pt-BR",
    timezone="America/Sao_Paulo",
    role=Role.USER,
    password_hash="$argon2id$placeholder",
    email_verified_at=_BASE_TIME,
)


class FakePasswordAuthService:
    def __init__(self) -> None:
        self.result = AuthResult(
            user=_USER,
            access_token="access-token",
            expires_in_seconds=900,
            refresh_token="refresh-token",
            refresh_expires_at=_BASE_TIME + timedelta(days=7),
        )
        self.error: Exception | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.sent_email = render_auth_email(
            kind="verify_email",
            to=_USER.email,
            locale="pt-BR",
            link="https://app.example/verificar-email?token=abc",
        )

    def _record(self, operation: str, **payload: Any) -> None:
        self.calls.append((operation, payload))
        if self.error is not None:
            raise self.error

    async def register(self, **kwargs: Any) -> Any:
        self._record("register", **kwargs)
        return self.sent_email

    async def login(self, **kwargs: Any) -> AuthResult:
        self._record("login", **kwargs)
        return self.result

    async def verify_email(self, **kwargs: Any) -> None:
        self._record("verify_email", **kwargs)

    async def resend_verification(self, **kwargs: Any) -> Any:
        self._record("resend_verification", **kwargs)
        return self.sent_email

    async def forgot_password(self, **kwargs: Any) -> Any:
        self._record("forgot_password", **kwargs)
        return self.sent_email

    async def reset_password(self, **kwargs: Any) -> Any:
        self._record("reset_password", **kwargs)
        return self.sent_email

    async def change_password(self, **kwargs: Any) -> None:
        self._record("change_password", **kwargs)


class FakeLimiter:
    def __init__(self) -> None:
        self.blocked = False
        self.calls: list[tuple[str, str | None]] = []

    async def consume(
        self,
        scope: str,
        *,
        ip: str,
        identifier: str | None,
    ) -> Any:
        self.calls.append((scope, identifier))
        from paysentineliq.infrastructure.security.rate_limit import RateLimitResult

        return RateLimitResult(
            allowed=not self.blocked,
            remaining=1,
            retry_after_seconds=0 if not self.blocked else 120,
            degraded=False,
        )


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> None:
        self.sent.append(
            {"to": to, "subject": subject, "body": body, "html_body": html_body},
        )


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "local",
        "frontend_url": "https://app.example",
        "jwt_secret": "s" * 64,
        "security_hash_secret": "h" * 32,
        "auth_password_enabled": True,
        "auth_email_provider": "development",
        "auth_email_development_dir": "var/test-outbox",
    }
    values.update(overrides)
    return Settings(**values)


def _app(
    *,
    settings: Settings | None = None,
    service: FakePasswordAuthService | None = None,
    limiter: FakeLimiter | None = None,
    sender: FakeSender | None = None,
) -> tuple[FastAPI, FakePasswordAuthService, FakeLimiter, FakeSender]:
    resolved = settings or _settings()
    app = create_app(resolved)
    fake_service = service or FakePasswordAuthService()
    fake_limiter = limiter or FakeLimiter()
    fake_sender = sender or FakeSender()
    app.dependency_overrides[get_auth_service] = lambda: fake_service
    app.dependency_overrides[get_auth_rate_limiter] = lambda: fake_limiter
    app.dependency_overrides[get_auth_email_sender] = lambda: fake_sender
    return app, fake_service, fake_limiter, fake_sender


async def _post(
    app: FastAPI,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, json=json_body, headers=headers)


async def _get(app: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


async def test_capabilities_report_password_state() -> None:
    app, _, _, _ = _app()
    enabled = await _get(app, "/api/v1/auth/capabilities")

    disabled_app, _, _, _ = _app(
        settings=_settings(auth_password_enabled=False),
    )
    disabled = await _get(disabled_app, "/api/v1/auth/capabilities")

    assert enabled.json() == {
        "password_enabled": True,
        "signup_enabled": True,
        "password_reset_enabled": True,
        "google_enabled": False,
    }
    assert disabled.json() == {
        "password_enabled": False,
        "signup_enabled": False,
        "password_reset_enabled": False,
        "google_enabled": False,
    }


async def test_capabilities_without_email_provider_keeps_login_only() -> None:
    app, _, _, _ = _app(settings=_settings(auth_email_provider="disabled"))

    response = await _get(app, "/api/v1/auth/capabilities")

    body = response.json()
    assert body["password_enabled"] is True
    assert body["signup_enabled"] is False
    assert body["password_reset_enabled"] is False


async def test_password_policy_exposes_server_rules() -> None:
    app, _, _, _ = _app()

    response = await _get(app, "/api/v1/auth/password-policy")

    body = response.json()
    assert response.status_code == 200
    assert body["min_length"] == 10
    assert body["max_length"] == 128


async def test_register_returns_neutral_accepted_and_schedules_email() -> None:
    app, service, limiter, sender = _app()

    response = await _post(
        app,
        "/api/v1/auth/register",
        json_body={
            "nome_completo": "Pessoa Exemplo",
            "email": "Pessoa@Example.com",
            "senha": "frase secreta longa",
            "aceite_termos": True,
            "aceite_privacidade": True,
        },
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert "token" not in response.text
    assert service.calls[0][0] == "register"
    assert service.calls[0][1]["email"] == "pessoa@example.com"
    assert limiter.calls == [("register", "pessoa@example.com")]
    assert sender.sent and sender.sent[0]["to"] == "pessoa@example.com"


async def test_register_requires_both_consents() -> None:
    app, _, _, _ = _app()

    response = await _post(
        app,
        "/api/v1/auth/register",
        json_body={
            "nome_completo": "Pessoa Exemplo",
            "email": "pessoa@example.com",
            "senha": "frase secreta longa",
            "aceite_termos": True,
            "aceite_privacidade": False,
        },
    )

    assert response.status_code == 422


async def test_register_rejects_extra_fields_and_bad_email() -> None:
    app, _, _, _ = _app()

    extra = await _post(
        app,
        "/api/v1/auth/register",
        json_body={
            "nome_completo": "Pessoa Exemplo",
            "email": "pessoa@example.com",
            "senha": "frase secreta longa",
            "aceite_termos": True,
            "aceite_privacidade": True,
            "role": "admin",
        },
    )
    bad_email = await _post(
        app,
        "/api/v1/auth/register",
        json_body={
            "nome_completo": "Pessoa Exemplo",
            "email": "sem-arroba",
            "senha": "frase secreta longa",
            "aceite_termos": True,
            "aceite_privacidade": True,
        },
    )

    assert extra.status_code == 422
    assert bad_email.status_code == 422


async def test_password_routes_are_disabled_without_flag() -> None:
    app, _, _, _ = _app(settings=_settings(auth_password_enabled=False))

    response = await _post(
        app,
        "/api/v1/auth/login",
        json_body={"email": "pessoa@example.com", "senha": "frase secreta longa"},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "auth_not_configured"


async def test_login_sets_cookies_and_hides_access_token_from_body_headers() -> None:
    app, service, _, _ = _app()

    response = await _post(
        app,
        "/api/v1/auth/login",
        json_body={"email": "pessoa@example.com", "senha": "frase secreta longa"},
    )

    assert response.status_code == 200
    cookies = "\n".join(response.headers.get_list("set-cookie"))
    assert "refresh_token=" in cookies
    assert "HttpOnly" in cookies
    assert "csrf_token=" in cookies
    assert service.calls[0][0] == "login"
    assert response.json()["user"]["email"] == "pessoa@example.com"


async def test_login_error_is_generic() -> None:
    service = FakePasswordAuthService()
    service.error = InvalidCredentialsError()
    app, _, _, _ = _app(service=service)

    response = await _post(
        app,
        "/api/v1/auth/login",
        json_body={"email": "pessoa@example.com", "senha": "senha errada"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


async def test_login_unverified_returns_specific_code() -> None:
    service = FakePasswordAuthService()
    service.error = AccountNotVerifiedError()
    app, _, _, _ = _app(service=service)

    response = await _post(
        app,
        "/api/v1/auth/login",
        json_body={"email": "pessoa@example.com", "senha": "frase secreta longa"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"


async def test_login_rate_limited_includes_retry_after() -> None:
    limiter = FakeLimiter()
    limiter.blocked = True
    app, service, _, _ = _app(limiter=limiter)

    response = await _post(
        app,
        "/api/v1/auth/login",
        json_body={"email": "pessoa@example.com", "senha": "frase secreta longa"},
    )

    assert response.status_code == 429
    assert response.headers.get("retry-after") == "120"
    assert service.calls == []


async def test_password_policy_error_exposes_violations_only() -> None:
    service = FakePasswordAuthService()
    service.error = PasswordPolicyError(("too_short",))
    app, _, _, _ = _app(service=service)

    response = await _post(
        app,
        "/api/v1/auth/register",
        json_body={
            "nome_completo": "Pessoa Exemplo",
            "email": "pessoa@example.com",
            "senha": "curta",
            "aceite_termos": True,
            "aceite_privacidade": True,
        },
    )

    assert response.status_code == 422
    assert response.json()["violations"] == ["too_short"]


async def test_verify_email_and_reset_are_neutral_on_success() -> None:
    app, service, _, _ = _app()

    verified = await _post(
        app,
        "/api/v1/auth/verify-email",
        json_body={"token": "a" * 43},
    )
    reset = await _post(
        app,
        "/api/v1/auth/reset-password",
        json_body={"token": "b" * 43, "nova_senha": "nova frase bem longa"},
    )

    assert verified.status_code == 204
    assert reset.status_code == 204
    assert [call[0] for call in service.calls] == ["verify_email", "reset_password"]


async def test_invalid_token_returns_generic_error() -> None:
    service = FakePasswordAuthService()
    service.error = InvalidAuthTokenError()
    app, _, _, _ = _app(service=service)

    response = await _post(
        app,
        "/api/v1/auth/verify-email",
        json_body={"token": "a" * 43},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_auth_token"
    assert "expired" not in response.text.lower() or "invalid" in response.text.lower()


async def test_forgot_and_resend_are_neutral_for_unknown_email() -> None:
    service = FakePasswordAuthService()

    async def forgot_password(**kwargs: Any) -> None:
        service.calls.append(("forgot_password", kwargs))
        return None

    service.forgot_password = forgot_password  # type: ignore[method-assign]
    app, _, _, sender = _app(service=service)

    response = await _post(
        app,
        "/api/v1/auth/forgot-password",
        json_body={"email": "ninguem@example.com"},
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    assert sender.sent == []


async def test_resend_and_forgot_share_neutral_payload() -> None:
    app, _, limiter, _ = _app()

    resend = await _post(
        app,
        "/api/v1/auth/resend-verification",
        json_body={"email": "pessoa@example.com"},
    )
    forgot = await _post(
        app,
        "/api/v1/auth/forgot-password",
        json_body={"email": "pessoa@example.com"},
    )

    assert resend.json() == forgot.json() == {"status": "accepted"}
    assert [call[0] for call in limiter.calls] == ["resend", "forgot"]


async def test_change_password_requires_authentication() -> None:
    app, _, _, _ = _app()

    response = await _post(
        app,
        "/api/v1/auth/change-password",
        json_body={"senha_atual": "frase secreta longa", "nova_senha": "nova frase bem longa"},
    )

    assert response.status_code == 401


async def test_too_many_attempts_from_service_carries_retry_after() -> None:
    service = FakePasswordAuthService()
    service.error = TooManyAttemptsError(45)
    app, _, _, _ = _app(service=service)

    response = await _post(
        app,
        "/api/v1/auth/login",
        json_body={"email": "pessoa@example.com", "senha": "frase secreta longa"},
    )

    assert response.status_code == 429
    assert response.headers.get("retry-after") == "45"
