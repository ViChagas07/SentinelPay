import httpx
import pytest
from fastapi import FastAPI

from paysentineliq.application.ports.readiness import ReadinessStatus
from paysentineliq.infrastructure.config import Settings
from paysentineliq.interface.api.dependencies import get_readiness_checker
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit


class StubChecker:
    def __init__(self, status: ReadinessStatus) -> None:
        self._status = status

    async def check(self) -> ReadinessStatus:
        return self._status


def _app(status: ReadinessStatus) -> FastAPI:
    app = create_app(Settings(app_env="local"))
    app.dependency_overrides[get_readiness_checker] = lambda: StubChecker(status)
    return app


async def _get(app: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


async def test_ready_when_all_dependencies_are_up() -> None:
    response = await _get(_app(ReadinessStatus(database=True, cache=True)), "/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"postgres": True, "redis": True},
    }


async def test_not_ready_when_cache_is_down() -> None:
    response = await _get(_app(ReadinessStatus(database=True, cache=False)), "/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"postgres": True, "redis": False},
    }


async def test_not_ready_when_database_is_down() -> None:
    response = await _get(_app(ReadinessStatus(database=False, cache=True)), "/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["postgres"] is False
