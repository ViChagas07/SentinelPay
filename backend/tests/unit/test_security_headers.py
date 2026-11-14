import httpx
import pytest
from fastapi import FastAPI

from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.security.rate_limit import RateLimitResult
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit


class DeniedLimiter:
    async def consume(self, identity: str) -> RateLimitResult:
        return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=2)


def _local_app() -> FastAPI:
    return create_app(Settings(app_env="local"))


def _production_app() -> FastAPI:
    return create_app(
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://user:pass@db:5432/app",
            redis_url="redis://cache:6379/0",
            security_hash_secret="production-secret",
            jwt_secret="x" * 64,
            google_client_id="test-client",
            google_client_secret="test-secret",
            google_redirect_uri="https://example.com/api/v1/auth/google/callback",
            frontend_url="https://app.example.com",
        )
    )


async def _get(
    app: FastAPI,
    path: str = "/health",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=headers)


async def test_security_headers_on_local_response() -> None:
    response = await _get(_local_app())

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" not in response.headers


async def test_hsts_is_added_outside_local() -> None:
    response = await _get(_production_app())

    assert response.status_code == 200
    assert "max-age=31536000" in response.headers["Strict-Transport-Security"]


async def test_docs_are_disabled_outside_local() -> None:
    response = await _get(_production_app(), "/docs")

    assert response.status_code == 404


async def test_cors_allows_configured_origin() -> None:
    response = await _get(_local_app(), headers={"Origin": "http://localhost:3000"})

    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"


async def test_cors_rejects_unknown_origin() -> None:
    response = await _get(_local_app(), headers={"Origin": "http://evil.example"})

    assert "Access-Control-Allow-Origin" not in response.headers


async def test_trusted_host_rejects_unknown_host() -> None:
    response = await _get(_local_app(), headers={"Host": "evil.example"})

    assert response.status_code == 400


async def test_rate_limited_response_keeps_security_headers() -> None:
    app = _local_app()

    @app.get("/api/v1/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    app.state.rate_limiter = DeniedLimiter()

    response = await _get(app, "/api/v1/ping")

    assert response.status_code == 429
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
