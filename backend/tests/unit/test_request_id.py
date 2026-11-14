import httpx
import pytest

from paysentineliq.interface.api.main import app

pytestmark = pytest.mark.unit


async def _get(headers: dict[str, str] | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/health", headers=headers)


async def test_generates_request_id_when_missing() -> None:
    response = await _get()

    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None
    assert len(request_id) == 36


async def test_echoes_safe_request_id() -> None:
    response = await _get(headers={"X-Request-ID": "req-safe_123"})

    assert response.headers["X-Request-ID"] == "req-safe_123"


async def test_replaces_unsafe_request_id() -> None:
    unsafe = "bad request id with spaces"

    response = await _get(headers={"X-Request-ID": unsafe})

    request_id = response.headers["X-Request-ID"]
    assert request_id != unsafe
    assert len(request_id) == 36
