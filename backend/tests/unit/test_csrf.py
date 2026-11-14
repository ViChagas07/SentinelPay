from typing import Annotated

import httpx
import pytest
from fastapi import Depends, FastAPI
from starlette.responses import Response

from paysentineliq.infrastructure.config import Settings
from paysentineliq.interface.api.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    generate_csrf_token,
    require_csrf,
    set_csrf_cookie,
)
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit


def _app() -> FastAPI:
    app = create_app(Settings(app_env="local"))

    @app.post("/api/v1/csrf-probe")
    async def probe(
        _: Annotated[None, Depends(require_csrf)],
    ) -> dict[str, str]:
        return {"status": "ok"}

    return app


async def _post(app: FastAPI, headers: dict[str, str] | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/v1/csrf-probe", headers=headers)


async def test_csrf_requires_cookie_and_header() -> None:
    response = await _post(_app())

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "csrf_invalid"


async def test_csrf_rejects_mismatched_tokens() -> None:
    response = await _post(
        _app(),
        headers={
            "Cookie": f"{CSRF_COOKIE_NAME}=token-a",
            CSRF_HEADER_NAME: "token-b",
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_invalid"


async def test_csrf_accepts_matching_tokens() -> None:
    token = generate_csrf_token()

    response = await _post(
        _app(),
        headers={
            "Cookie": f"{CSRF_COOKIE_NAME}={token}",
            CSRF_HEADER_NAME: token,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_csrf_cookie_is_readable_and_secure_when_requested() -> None:
    response = Response()
    token = generate_csrf_token()

    set_csrf_cookie(response, token, secure=True)

    cookie = response.headers["set-cookie"]
    assert f"{CSRF_COOKIE_NAME}={token}" in cookie
    assert "HttpOnly" not in cookie
    assert "Secure" in cookie
    assert "samesite=lax" in cookie.lower()
