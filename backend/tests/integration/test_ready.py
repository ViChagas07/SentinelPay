import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_ready_via_compose() -> None:
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=5.0) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"postgres": True, "redis": True},
    }
