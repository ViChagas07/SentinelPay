from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.retrieval.runtime import RetrievalRuntime
from paysentineliq.interface.api.main import create_app
from tests.support.retrieval_fakes import FakeEmbedder, FakeReranker

pytestmark = pytest.mark.unit


async def _get(app: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


async def test_lifespan_loads_once_and_health_reports_loaded_models() -> None:
    settings = Settings(app_env="local")
    app = create_app(settings)
    embedder = FakeEmbedder()
    reranker = FakeReranker()
    runtime = RetrievalRuntime(settings, embedder=embedder, reranker=reranker)
    app.state.retrieval_runtime = runtime

    async with app.router.lifespan_context(app):
        response = await _get(app, "/health")

        assert embedder.loads == 1
        assert reranker.loads == 1
        assert response.status_code == 200
        assert response.json()["retrieval"]["embedder"]["loaded"] is True
        assert response.json()["retrieval"]["reranker"]["loaded"] is True

    assert embedder.loads == 1
    assert embedder.closes == 1


async def test_lifespan_survives_missing_model_files(tmp_path: Path) -> None:
    settings = Settings(
        app_env="local",
        retrieval_model_dir=str(tmp_path),
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        response = await _get(app, "/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["retrieval"]["embedder"]["loaded"] is False
    assert body["retrieval"]["embedder"]["error"] == "model_files_missing"
    assert body["retrieval"]["reranker"]["loaded"] is False
