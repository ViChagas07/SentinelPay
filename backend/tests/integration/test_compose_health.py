import os

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_health_via_compose() -> None:
    base_url = os.environ.get("API_BASE_URL", "http://localhost:8000")

    async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
