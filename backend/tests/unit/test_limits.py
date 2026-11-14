import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from paysentineliq.infrastructure.config import Settings
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit


async def _request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    content: bytes | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, content=content)


async def test_body_over_limit_returns_413() -> None:
    app = create_app(Settings(app_env="local", max_request_body_bytes=10))

    @app.post("/api/v1/echo")
    async def echo(payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    response = await _request(
        app,
        "POST",
        "/api/v1/echo",
        content=b'{"text":"' + b"a" * 32 + b'"}',
    )

    assert response.status_code == 413
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "request_too_large"


async def test_chunked_body_over_limit_returns_413() -> None:
    app = create_app(Settings(app_env="local", max_request_body_bytes=10))

    @app.post("/api/v1/echo")
    async def echo(payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    async def chunks() -> AsyncIterator[bytes]:
        yield b'{"text":"'
        yield b"a" * 32
        yield b'"}'

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/echo", content=chunks())

    assert response.status_code == 413, response.text
    assert response.json()["code"] == "request_too_large"


async def test_slow_route_returns_504() -> None:
    app = create_app(Settings(app_env="local", request_timeout_seconds=0.01))

    @app.get("/api/v1/slow")
    async def slow() -> dict[str, str]:
        await asyncio.sleep(0.1)
        return {"status": "ok"}

    response = await _request(app, "GET", "/api/v1/slow")

    assert response.status_code == 504
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "request_timeout"


async def test_health_response_is_json() -> None:
    response = await _request(
        create_app(Settings(app_env="local")),
        "GET",
        "/health",
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
