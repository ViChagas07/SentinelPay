from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from paysentineliq.application.commands.auth import AuthResult
from paysentineliq.application.errors import (
    InvalidRefreshTokenError,
    OAuthAuthenticationError,
)
from paysentineliq.application.ports.oidc import GoogleIdentity
from paysentineliq.application.ports.oidc_state import OIDCState
from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.security.bruteforce import BruteForceStatus
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService
from paysentineliq.interface.api.dependencies import (
    get_auth_service,
    get_auth_unit_of_work,
    get_brute_force,
    get_oidc_client,
    get_oidc_state_store,
)
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit

_BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)
_IDENTITY = GoogleIdentity(
    google_sub="google-sub",
    email="user@example.com",
    name="User",
)
_USER = User(
    id=uuid4(),
    google_sub="google-sub",
    email="user@example.com",
    name="User",
    preferred_locale="pt-BR",
    timezone="America/Sao_Paulo",
    role=Role.USER,
)
_ADMIN = replace(_USER, id=uuid4(), role=Role.ADMIN)


class FakeOIDCClient:
    def __init__(self) -> None:
        self.identity = _IDENTITY
        self.error: Exception | None = None
        self.last_state = ""
        self.last_nonce = ""
        self.last_verifier = ""

    async def authorization_url(self, *, state: str, nonce: str, code_verifier: str) -> str:
        self.last_state = state
        self.last_nonce = nonce
        self.last_verifier = code_verifier
        return f"https://google.test/auth?state={state}&nonce={nonce}"

    async def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
        expected_nonce: str,
    ) -> GoogleIdentity:
        if self.error is not None:
            raise self.error
        return self.identity


class FakeStateStore:
    def __init__(self) -> None:
        self.states: dict[str, OIDCState] = {}

    async def save(self, state: str, data: OIDCState, ttl_seconds: int) -> None:
        self.states[state] = data

    async def pop(self, state: str) -> OIDCState | None:
        return self.states.pop(state, None)


class FakeAuthService:
    def __init__(self) -> None:
        self.result = AuthResult(
            user=_USER,
            access_token="access-token",
            expires_in_seconds=900,
            refresh_token="refresh-token",
            refresh_expires_at=_BASE_TIME + timedelta(days=7),
        )
        self.refresh_error: Exception | None = None
        self.login_calls: list[GoogleIdentity] = []
        self.refresh_calls: list[str] = []
        self.logout_calls: list[tuple[str | None, object]] = []

    async def login_with_google(
        self,
        identity: GoogleIdentity,
        context: object | None = None,
    ) -> AuthResult:
        self.login_calls.append(identity)
        return self.result

    async def refresh(self, raw_refresh_token: str) -> AuthResult:
        self.refresh_calls.append(raw_refresh_token)
        if self.refresh_error is not None:
            raise self.refresh_error
        return self.result

    async def logout(
        self,
        raw_refresh_token: str | None,
        access_claims: object,
        context: object | None = None,
    ) -> None:
        self.logout_calls.append((raw_refresh_token, access_claims))


class FakeBruteForce:
    def __init__(self) -> None:
        self.blocked = False
        self.retry_after = 30
        self.failures: list[tuple[str, str]] = []
        self.resets: list[tuple[str, str]] = []

    async def check(self, *, identifier: str, ip: str) -> BruteForceStatus:
        return BruteForceStatus(
            blocked=self.blocked,
            retry_after_seconds=self.retry_after if self.blocked else 0,
            failures=0,
        )

    async def record_failure(self, *, identifier: str, ip: str) -> BruteForceStatus:
        self.failures.append((identifier, ip))
        return BruteForceStatus(False, 0, 0)

    async def reset(self, *, identifier: str, ip: str) -> None:
        self.resets.append((identifier, ip))


class FakeRevokedStore:
    def __init__(self) -> None:
        self.revoked: set[str] = set()

    async def revoke(self, jti: str, expires_at: int) -> None:
        self.revoked.add(jti)

    async def is_revoked(self, jti: str) -> bool:
        return jti in self.revoked


class FakeUsers:
    def __init__(self, user: User) -> None:
        self.user = user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.user if user_id == self.user.id else None


class FakeAuthUow:
    def __init__(self, user: User) -> None:
        self.users = FakeUsers(user)

    async def __aenter__(self) -> "FakeAuthUow":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "local",
        "google_client_id": "client",
        "google_client_secret": "secret",
        "google_redirect_uri": "https://app.example/api/v1/auth/google/callback",
        "frontend_url": "https://frontend.example",
        "jwt_secret": "s" * 64,
        "security_hash_secret": "h" * 32,
        "oidc_state_ttl_seconds": 600,
    }
    values.update(overrides)
    return Settings(**values)


def _auth_app(
    *,
    settings: Settings | None = None,
    oidc: FakeOIDCClient | None = None,
    state_store: FakeStateStore | None = None,
    auth_service: FakeAuthService | None = None,
    brute_force: FakeBruteForce | None = None,
) -> tuple[
    FastAPI,
    FakeOIDCClient,
    FakeStateStore,
    FakeAuthService,
    FakeBruteForce,
]:
    resolved_settings = settings or _settings()
    app = create_app(resolved_settings)
    app.state.token_service = JwtAccessTokenService(
        secret=resolved_settings.jwt_secret,
        ttl_minutes=15,
    )
    app.state.revoked_tokens = FakeRevokedStore()
    fake_oidc = oidc or FakeOIDCClient()
    fake_store = state_store or FakeStateStore()
    fake_auth = auth_service or FakeAuthService()
    fake_brute = brute_force or FakeBruteForce()
    app.dependency_overrides[get_oidc_client] = lambda: fake_oidc
    app.dependency_overrides[get_oidc_state_store] = lambda: fake_store
    app.dependency_overrides[get_auth_service] = lambda: fake_auth
    app.dependency_overrides[get_brute_force] = lambda: fake_brute
    app.dependency_overrides[get_auth_unit_of_work] = lambda: FakeAuthUow(_USER)
    return app, fake_oidc, fake_store, fake_auth, fake_brute


async def _request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request_headers = dict(headers or {})
    if cookies:
        cookie_header = "; ".join(f"{key}={value}" for key, value in cookies.items())
        existing = request_headers.get("Cookie")
        request_headers["Cookie"] = f"{existing}; {cookie_header}" if existing else cookie_header
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(
            method,
            path,
            headers=request_headers,
        )


def _set_cookies(response: httpx.Response) -> str:
    return "\n".join(response.headers.get_list("set-cookie"))


async def test_login_redirects_with_state_cookie_and_pkce() -> None:
    app, oidc, store, _, _ = _auth_app()

    response = await _request(app, "GET", "/api/v1/auth/google/login")

    assert response.status_code == 302
    assert "https://google.test/auth" in response.headers["location"]
    assert oidc.last_state in store.states
    cookie = _set_cookies(response)
    assert "oidc_state=" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/api/v1/auth/google" in cookie


async def test_login_requires_google_configuration() -> None:
    settings = _settings(google_client_id="")
    app, _, _, _, _ = _auth_app(settings=settings)

    response = await _request(app, "GET", "/api/v1/auth/google/login")

    assert response.status_code == 503
    assert response.json()["code"] == "auth_not_configured"


async def test_callback_sets_cookies_and_redirects_without_tokens() -> None:
    app, _oidc, store, auth_service, brute = _auth_app()
    state = "state-value"
    store.states[state] = OIDCState(
        nonce="nonce",
        code_verifier="verifier",
        redirect_uri="https://app.example/callback",
    )

    response = await _request(
        app,
        "GET",
        f"/api/v1/auth/google/callback?code=code&state={state}",
        cookies={"oidc_state": state},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "https://frontend.example"
    assert auth_service.login_calls == [_IDENTITY]
    assert state not in store.states
    assert brute.resets
    cookies = _set_cookies(response)
    assert "refresh_token=refresh-token" in cookies
    assert "HttpOnly" in cookies
    assert "csrf_token=" in cookies
    assert "oidc_state=" in cookies


async def test_callback_rejects_invalid_state() -> None:
    app, _, _, auth_service, brute = _auth_app()

    response = await _request(
        app,
        "GET",
        "/api/v1/auth/google/callback?code=code&state=wrong",
        cookies={"oidc_state": "other"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_state"
    assert auth_service.login_calls == []
    assert brute.failures


async def test_callback_blocks_bruteforce() -> None:
    app, _, store, auth_service, brute = _auth_app()
    state = "blocked-state"
    store.states[state] = OIDCState("nonce", "verifier", "https://callback")
    brute.blocked = True

    response = await _request(
        app,
        "GET",
        f"/api/v1/auth/google/callback?code=code&state={state}",
        cookies={"oidc_state": state},
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
    assert response.json()["code"] == "too_many_attempts"
    assert auth_service.login_calls == []


async def test_callback_records_oidc_failure() -> None:
    app, oidc, store, auth_service, brute = _auth_app()
    state = "oidc-error-state"
    store.states[state] = OIDCState("nonce", "verifier", "https://callback")
    oidc.error = OAuthAuthenticationError()

    response = await _request(
        app,
        "GET",
        f"/api/v1/auth/google/callback?code=code&state={state}",
        cookies={"oidc_state": state},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "google_auth_failed"
    assert auth_service.login_calls == []
    assert brute.failures


async def test_refresh_requires_csrf() -> None:
    app, _, _, auth_service, _ = _auth_app()

    response = await _request(
        app,
        "POST",
        "/api/v1/auth/refresh",
        cookies={"refresh_token": "raw"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_invalid"
    assert auth_service.refresh_calls == []


async def test_refresh_rotates_cookies_and_returns_access() -> None:
    app, _, _, auth_service, brute = _auth_app()

    response = await _request(
        app,
        "POST",
        "/api/v1/auth/refresh",
        cookies={"refresh_token": "old", "csrf_token": "csrf"},
        headers={"X-CSRF-Token": "csrf"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "access-token"
    assert response.json()["user"]["role"] == "user"
    assert auth_service.refresh_calls == ["old"]
    assert brute.resets
    cookies = _set_cookies(response)
    assert "refresh_token=refresh-token" in cookies
    assert "csrf_token=" in cookies


async def test_refresh_invalid_token_clears_cookies() -> None:
    app, _, _, auth_service, brute = _auth_app()
    auth_service.refresh_error = InvalidRefreshTokenError()

    response = await _request(
        app,
        "POST",
        "/api/v1/auth/refresh",
        cookies={"refresh_token": "bad", "csrf_token": "csrf"},
        headers={"X-CSRF-Token": "csrf"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_refresh_token"
    cookies = _set_cookies(response)
    assert "refresh_token=" in cookies
    assert "csrf_token=" in cookies
    assert brute.failures


async def test_logout_requires_csrf() -> None:
    app, _, _, auth_service, _ = _auth_app()

    response = await _request(
        app,
        "POST",
        "/api/v1/auth/logout",
        cookies={"refresh_token": "raw"},
    )

    assert response.status_code == 403
    assert auth_service.logout_calls == []


async def test_logout_clears_cookies_and_revokes_refresh() -> None:
    app, _, _, auth_service, _ = _auth_app()

    response = await _request(
        app,
        "POST",
        "/api/v1/auth/logout",
        cookies={"refresh_token": "raw", "csrf_token": "csrf"},
        headers={"X-CSRF-Token": "csrf"},
    )

    assert response.status_code == 204
    assert auth_service.logout_calls
    cookies = _set_cookies(response)
    assert "refresh_token=" in cookies
    assert "csrf_token=" in cookies


async def test_protected_routes_reject_anonymous() -> None:
    app, _, _, _, _ = _auth_app()

    me = await _request(app, "GET", "/api/v1/users/me")
    user = await _request(app, "GET", "/api/v1/protected/user")

    assert me.status_code == 401
    assert user.status_code == 401
    assert me.json()["code"] == "invalid_access_token"


def _protected_app(user: User) -> tuple[FastAPI, JwtAccessTokenService, FakeRevokedStore]:
    settings = _settings()
    app = create_app(settings)
    token_service = JwtAccessTokenService(
        secret=settings.jwt_secret,
        ttl_minutes=15,
    )
    revoked = FakeRevokedStore()
    app.state.token_service = token_service
    app.state.revoked_tokens = revoked
    app.dependency_overrides[get_auth_unit_of_work] = lambda: FakeAuthUow(user)
    return app, token_service, revoked


async def test_user_can_access_user_but_not_admin() -> None:
    app, token_service, _ = _protected_app(_USER)
    token = token_service.issue(_USER).token
    headers = {"Authorization": f"Bearer {token}"}

    me = await _request(app, "GET", "/api/v1/users/me", headers=headers)
    user_route = await _request(app, "GET", "/api/v1/protected/user", headers=headers)
    admin_route = await _request(app, "GET", "/api/v1/protected/admin", headers=headers)

    assert me.status_code == 200
    assert me.json()["email"] == _USER.email
    assert user_route.status_code == 200
    assert admin_route.status_code == 403
    assert admin_route.json()["code"] == "forbidden"


async def test_admin_can_access_admin_route() -> None:
    app, token_service, _ = _protected_app(_ADMIN)
    token = token_service.issue(_ADMIN).token

    response = await _request(
        app,
        "GET",
        "/api/v1/protected/admin",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_db_role_wins_over_token_role() -> None:
    app, token_service, _ = _protected_app(_USER)
    admin_claim_token = token_service.issue(replace(_USER, role=Role.ADMIN)).token

    response = await _request(
        app,
        "GET",
        "/api/v1/protected/admin",
        headers={"Authorization": f"Bearer {admin_claim_token}"},
    )

    assert response.status_code == 403


async def test_revoked_jti_is_rejected() -> None:
    app, token_service, revoked = _protected_app(_USER)
    issued = token_service.issue(_USER)
    revoked.revoked.add(issued.claims.jti)

    response = await _request(
        app,
        "GET",
        "/api/v1/protected/user",
        headers={"Authorization": f"Bearer {issued.token}"},
    )

    assert response.status_code == 401


async def test_tampered_access_token_is_rejected() -> None:
    app, token_service, _ = _protected_app(_USER)
    token = token_service.issue(_USER).token
    header, payload, signature = token.split(".")
    tampered = ".".join([header, payload[:-1] + ("A" if payload[-1] != "A" else "B"), signature])

    response = await _request(
        app,
        "GET",
        "/api/v1/protected/user",
        headers={"Authorization": f"Bearer {tampered}"},
    )

    assert response.status_code == 401
