from uuid import UUID, uuid4

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def _get(path: str, headers: dict[str, str]) -> httpx.Response:
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=5.0) as client:
        return await client.get(path, headers=headers)


async def test_example_route_uses_db_and_propagates_request_id() -> None:
    item_id = uuid4()

    response = await _get(
        f"/api/v1/example/{item_id}",
        headers={"X-Request-ID": "req-docker", "Accept-Language": "de"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-docker"
    body = response.json()
    assert body["item_id"] == str(item_id)
    assert body["request_id"] == "req-docker"
    assert body["locale"] == "de"


async def test_example_route_returns_problem_json_for_missing_document() -> None:
    response = await _get(
        f"/api/v1/example/{UUID(int=0)}",
        headers={"X-Request-ID": "req-docker-missing"},
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "document_not_found"
    assert body["request_id"] == "req-docker-missing"
