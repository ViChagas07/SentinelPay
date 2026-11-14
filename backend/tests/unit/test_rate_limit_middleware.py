from collections.abc import Awaitable, Callable

import httpx
import pytest
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.security.rate_limit import RateLimitResult
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit

LimiterCall = Callable[[str], Awaitable[RateLimitResult]]


class FakeLimiter:
    def __init__(self, results: list[RateLimitResult]) -> None:
        self._results = results
        self.identities: list[str] = []

    async def consume(self, identity: str) -> RateLimitResult:
        self.identities.append(identity)
        if not self._results:
            return RateLimitResult(allowed=True, remaining=1, retry_after_seconds=0)
        return self._results.pop(0)


class SetUserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.user_id = "user-1"
        return await call_next(request)


def _app(limiter: FakeLimiter, *, with_user: bool = False) -> FastAPI:
    app = create_app(Settings(app_env="local"))

    @app.get("/api/v1/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/auth/login")
    async def login() -> dict[str, str]:
        return {"status": "ok"}

    app.state.rate_limiter = limiter
    if with_user:
        app.add_middleware(SetUserMiddleware)
    return app


async def _get(app: FastAPI, path: str, headers: dict[str, str] | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=headers)


async def test_rate_limit_returns_429_with_retry_after() -> None:
    limiter = FakeLimiter([RateLimitResult(allowed=False, remaining=0, retry_after_seconds=7)])

    response = await _get(_app(limiter), "/api/v1/ping", headers={"X-Request-ID": "rl-1"})

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"
    assert response.headers["X-Request-ID"] == "rl-1"
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "rate_limited"
    assert body["request_id"] == "rl-1"
    assert limiter.identities and limiter.identities[0].startswith("ip:")


async def test_health_is_not_rate_limited() -> None:
    limiter = FakeLimiter([])

    response = await _get(_app(limiter), "/health")

    assert response.status_code == 200
    assert limiter.identities == []


async def test_rate_limit_fails_open_outside_auth() -> None:
    limiter = FakeLimiter(
        [RateLimitResult(allowed=True, remaining=None, retry_after_seconds=0, degraded=True)]
    )

    response = await _get(_app(limiter), "/api/v1/ping")

    assert response.status_code == 200


async def test_rate_limit_fails_closed_on_auth_routes() -> None:
    limiter = FakeLimiter(
        [RateLimitResult(allowed=True, remaining=None, retry_after_seconds=0, degraded=True)]
    )

    response = await _get(_app(limiter), "/api/v1/auth/login")

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "rate_limit_unavailable"


async def test_rate_limit_checks_user_bucket_when_authenticated() -> None:
    limiter = FakeLimiter(
        [
            RateLimitResult(allowed=True, remaining=9, retry_after_seconds=0),
            RateLimitResult(allowed=False, remaining=0, retry_after_seconds=3),
        ]
    )

    response = await _get(_app(limiter, with_user=True), "/api/v1/ping")

    assert response.status_code == 429
    assert limiter.identities[0].startswith("ip:")
    assert limiter.identities[1] == "user:user-1"
