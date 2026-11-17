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
    body = response.json()
    assert body["status"] == "ok"
    assert body["retrieval"]["top_k"] == 25
    assert body["retrieval"]["rerank_top_n"] == 4
    assert body["retrieval"]["rerank_enabled"] is True
    assert body["retrieval"]["embedder"]["model"] == "BAAI/bge-m3"
    assert body["retrieval"]["sparse_embedder"]["model"] == "BAAI/bge-m3"
    assert body["retrieval"]["reranker"]["model"] == "BAAI/bge-reranker-v2-m3"
    assert body["retrieval"]["embedder"]["loaded"] is False


async def test_health_rejects_post() -> None:
    response = await _request("POST", "/health")

    assert response.status_code == 405
