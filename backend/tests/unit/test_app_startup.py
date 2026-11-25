from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI

from paysentineliq.application.ports.oidc_state import OIDCState
from paysentineliq.infrastructure.config import Settings
from paysentineliq.interface.api.dependencies import (
    get_oidc_client,
    get_oidc_state_store,
)
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit

_GOOGLE_ENV = {
    "app_env": "production",
    "database_url": "postgresql+asyncpg://user:pass@db:5432/app",
    "redis_url": "redis://cache:6379/0",
    "rabbitmq_url": "amqp://user:pass@rabbitmq:5672//",
    "celery_result_backend": "redis://cache:6379/1",
    "jwt_secret": "j" * 64,
    "s3_bucket": "bucket",
    "s3_access_key_id": "key",
    "s3_secret_access_key": "secret",
    "allowed_hosts": "testserver,localhost,127.0.0.1",
    "frontend_url": "https://app.example",
    "google_redirect_uri": "https://api.example/api/v1/auth/google/callback",
    "google_client_id": "client-id",
    "google_client_secret": "client-secret",
}


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = dict(_GOOGLE_ENV)
    values.update(overrides)
    return Settings(**values)


async def _get(app: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get(path)


class FakeOIDCClient:
    async def authorization_url(
        self,
        *,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> str:
        return (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?redirect_uri=https%3A%2F%2Fapi.example%2Fapi%2Fv1%2Fauth%2Fgoogle%2Fcallback"
            f"&state={state}&nonce={nonce}"
            "&code_challenge_method=S256"
        )


class FakeStateStore:
    def __init__(self) -> None:
        self.states: dict[str, OIDCState] = {}

    async def save(self, state: str, data: OIDCState, *, ttl_seconds: int) -> None:
        self.states[state] = data

    async def pop(self, state: str) -> OIDCState | None:
        return self.states.pop(state, None)


def test_app_imports_in_production_without_google_settings() -> None:
    settings = Settings(
        app_env="production",
        database_url=_GOOGLE_ENV["database_url"],
        redis_url=_GOOGLE_ENV["redis_url"],
        rabbitmq_url=_GOOGLE_ENV["rabbitmq_url"],
        celery_result_backend=_GOOGLE_ENV["celery_result_backend"],
        jwt_secret=_GOOGLE_ENV["jwt_secret"],
        s3_bucket=_GOOGLE_ENV["s3_bucket"],
        s3_access_key_id=_GOOGLE_ENV["s3_access_key_id"],
        s3_secret_access_key=_GOOGLE_ENV["s3_secret_access_key"],
        allowed_hosts=_GOOGLE_ENV["allowed_hosts"],
    )

    app = create_app(settings)

    assert settings.google_configured is False
    assert settings.google_configuration_missing == [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI",
        "FRONTEND_URL",
    ]
    assert app.title == "PaySentinelIQ"


def test_legacy_callback_path_only_disables_google_sign_in() -> None:
    settings = _settings(
        google_redirect_uri="https://api.example/api/auth/google/callback",
    )

    assert settings.google_configured is False
    assert settings.google_configuration_missing == [
        "GOOGLE_REDIRECT_URI(https://<api-host>/api/v1/auth/google/callback)",
    ]


async def test_smoke_health_and_auth_routes_survive_missing_google() -> None:
    app = create_app(
        Settings(
            app_env="production",
            database_url=_GOOGLE_ENV["database_url"],
            redis_url=_GOOGLE_ENV["redis_url"],
            rabbitmq_url=_GOOGLE_ENV["rabbitmq_url"],
            celery_result_backend=_GOOGLE_ENV["celery_result_backend"],
            jwt_secret=_GOOGLE_ENV["jwt_secret"],
            s3_bucket=_GOOGLE_ENV["s3_bucket"],
            s3_access_key_id=_GOOGLE_ENV["s3_access_key_id"],
            s3_secret_access_key=_GOOGLE_ENV["s3_secret_access_key"],
            allowed_hosts=_GOOGLE_ENV["allowed_hosts"],
        )
    )

    health = await _get(app, "/health")
    capabilities = await _get(app, "/api/v1/auth/capabilities")
    policy = await _get(app, "/api/v1/auth/password-policy")
    google = await _get(app, "/api/v1/auth/google/login")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert capabilities.status_code == 200
    assert capabilities.json()["google_enabled"] is False
    assert policy.status_code == 200
    assert google.status_code == 503
    body = google.json()
    assert body["code"] == "auth_not_configured"
    assert "GOOGLE_CLIENT_ID" in body["detail"]


async def test_google_login_redirects_with_fixed_redirect_uri() -> None:
    app = create_app(_settings())
    store = FakeStateStore()
    app.dependency_overrides[get_oidc_client] = lambda: FakeOIDCClient()
    app.dependency_overrides[get_oidc_state_store] = lambda: store

    response = await _get(app, "/api/v1/auth/google/login")

    assert response.status_code in {302, 307}
    location = urlparse(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == (
        "https://accounts.google.com/o/oauth2/v2/auth"
    )
    params = parse_qs(location.query)
    assert params["redirect_uri"] == ["https://api.example/api/v1/auth/google/callback"]
    assert params["state"]
    assert params["nonce"]
    assert params["code_challenge_method"] == ["S256"]
    assert list(store.states) == params["state"]
    cookie = "; ".join(response.headers.get_list("set-cookie"))
    assert "oidc_state=" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie


async def test_google_callback_returns_503_when_sign_in_is_disabled() -> None:
    app = create_app(
        Settings(
            app_env="production",
            database_url=_GOOGLE_ENV["database_url"],
            redis_url=_GOOGLE_ENV["redis_url"],
            rabbitmq_url=_GOOGLE_ENV["rabbitmq_url"],
            celery_result_backend=_GOOGLE_ENV["celery_result_backend"],
            jwt_secret=_GOOGLE_ENV["jwt_secret"],
            s3_bucket=_GOOGLE_ENV["s3_bucket"],
            s3_access_key_id=_GOOGLE_ENV["s3_access_key_id"],
            s3_secret_access_key=_GOOGLE_ENV["s3_secret_access_key"],
            allowed_hosts=_GOOGLE_ENV["allowed_hosts"],
        )
    )

    response = await _get(
        app,
        "/api/v1/auth/google/callback?code=code&state=state",
    )

    assert response.status_code == 503
    assert response.json()["code"] == "auth_not_configured"
