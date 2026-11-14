import io
import json
import logging
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from paysentineliq.domain.errors import NotFoundError
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.logging import JsonFormatter, PIIMaskingFilter
from paysentineliq.interface.api.dependencies import get_example_service
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit


class StubService:
    def __init__(self, found: bool) -> None:
        self._found = found

    async def check(self, item_id: UUID) -> bool:
        if not self._found:
            raise NotFoundError(
                code="document_not_found",
                message="Document not found.",
            )
        return True


def _app(found: bool = True) -> FastAPI:
    app = create_app(Settings(app_env="local"))
    app.dependency_overrides[get_example_service] = lambda: StubService(found)
    return app


async def _get(
    app: FastAPI,
    path: str,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=headers)


async def test_example_route_proves_session_contract() -> None:
    item_id = uuid4()

    response = await _get(
        _app(),
        f"/api/v1/example/{item_id}",
        headers={
            "Accept-Language": "fr;q=0.9,en;q=0.5",
            "X-Request-ID": "req-example",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-example"
    assert response.json() == {
        "item_id": str(item_id),
        "status": "ok",
        "locale": "fr",
        "request_id": "req-example",
    }


async def test_example_route_maps_not_found() -> None:
    response = await _get(
        _app(found=False),
        f"/api/v1/example/{UUID(int=0)}",
        headers={"X-Request-ID": "req-missing"},
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "document_not_found"
    assert body["request_id"] == "req-missing"


async def test_example_route_rejects_invalid_uuid() -> None:
    response = await _get(_app(), "/api/v1/example/not-a-uuid")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"


async def test_example_route_logs_masked_pii_with_request_id() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(PIIMaskingFilter())
    logger = logging.getLogger("paysentineliq")
    logger.addHandler(handler)

    try:
        response = await _get(
            _app(),
            f"/api/v1/example/{uuid4()}?emit_log=true",
            headers={"X-Request-ID": "req-log"},
        )
    finally:
        logger.removeHandler(handler)

    assert response.status_code == 200
    records = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    demo = next(record for record in records if "example_demo" in str(record.get("message", "")))
    message = str(demo["message"])
    assert demo["request_id"] == "req-log"
    assert "[REDACTED_EMAIL]" in message
    assert "[REDACTED_CPF]" in message
    assert "demo@example.com" not in message
    assert "123.456.789-00" not in message
