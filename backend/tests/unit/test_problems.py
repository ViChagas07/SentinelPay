import httpx
import pytest
from fastapi import FastAPI

from paysentineliq.domain.errors import NotFoundError
from paysentineliq.infrastructure.config import Settings
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit


async def _request(
    app: FastAPI,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, headers=headers)


def _test_app() -> FastAPI:
    app = create_app(Settings(app_env="local"))

    @app.get("/domain-error")
    async def domain_error() -> None:
        raise NotFoundError(code="document_not_found", message="Document not found.")

    @app.get("/internal-error")
    async def internal_error() -> None:
        raise RuntimeError("secret detail demo@example.com")

    @app.get("/validate")
    async def validate(value: int) -> dict[str, int]:
        return {"value": value}

    return app


async def test_domain_error_becomes_problem_json() -> None:
    response = await _request(
        _test_app(), "GET", "/domain-error", headers={"X-Request-ID": "req-problem"}
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["X-Request-ID"] == "req-problem"

    body = response.json()
    assert body["code"] == "document_not_found"
    assert body["status"] == 404
    assert body["request_id"] == "req-problem"
    assert body["instance"] == "/domain-error"
    assert "Traceback" not in response.text


async def test_unexpected_error_does_not_leak_details() -> None:
    response = await _request(
        _test_app(), "GET", "/internal-error", headers={"X-Request-ID": "req-500"}
    )

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["X-Request-ID"] == "req-500"

    body = response.json()
    assert body["code"] == "internal_error"
    assert body["request_id"] == "req-500"
    assert "secret detail" not in response.text
    assert "demo@example.com" not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text


async def test_unknown_route_becomes_problem_json() -> None:
    response = await _request(_test_app(), "GET", "/missing-route")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "not_found"


async def test_method_not_allowed_becomes_problem_json() -> None:
    response = await _request(_test_app(), "POST", "/health")

    assert response.status_code == 405
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "method_not_allowed"


async def test_validation_error_is_generic_and_safe() -> None:
    response = await _request(_test_app(), "GET", "/validate?value=zz-reflect-marker")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "validation_error"
    assert "zz-reflect-marker" not in response.text
