from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI, Request

from paysentineliq.interface.api.upload_limit import (
    UploadSizeLimitMiddleware,
)

pytestmark = pytest.mark.unit


def _app(max_bytes: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        UploadSizeLimitMiddleware,
        path="/upload",
        max_bytes=max_bytes,
    )

    @app.post("/upload")
    async def upload(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"size": len(body)}

    return app


async def _post(
    app: FastAPI,
    content: bytes | AsyncIterator[bytes],
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.post("/upload", content=content)


async def test_content_length_over_limit_returns_413() -> None:
    response = await _post(_app(10), b"x" * 20)

    assert response.status_code == 413
    assert response.json()["code"] == "upload_too_large"


async def test_chunked_body_over_limit_returns_413() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b"x" * 6
        yield b"y" * 6

    response = await _post(_app(10), chunks())

    assert response.status_code == 413
    assert response.json()["code"] == "upload_too_large"


async def test_body_within_limit_is_forwarded() -> None:
    response = await _post(_app(10), b"x" * 5)

    assert response.status_code == 200
    assert response.json() == {"size": 5}
