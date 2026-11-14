import httpx
import pytest

from paysentineliq.interface.api.main import app

pytestmark = pytest.mark.unit


async def _request(method: str, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path)


async def test_health_returns_ok() -> None:
    response = await _request("GET", "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_rejects_post() -> None:
    response = await _request("POST", "/health")

    assert response.status_code == 405
