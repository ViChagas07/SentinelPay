import json
from collections.abc import Mapping

import httpx
import pytest

from paysentineliq.application.errors import RerankTimeoutError, RetrievalUnavailableError
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.retrieval.remote_reranker import RemoteReranker

pytestmark = pytest.mark.unit


class FakeClient:
    def __init__(
        self,
        *,
        response: httpx.Response | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.method = ""
        self.url = ""
        self.payload: dict[str, object] = {}
        self.headers: dict[str, str] = {}
        self.allow_internal = False

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        content: bytes | None = None,
        allow_internal: bool = False,
    ) -> httpx.Response:
        self.method = method
        self.url = url
        self.payload = json.loads((content or b"{}").decode("utf-8"))
        self.headers = dict(headers or {})
        self.allow_internal = allow_internal
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "local",
        "reranker_backend": "remote",
        "reranker_remote_url": "http://localhost:9999/rerank",
        "reranker_remote_api_key": "secret",
        "reranker_remote_model": "remote-reranker",
        "rerank_max_length": 128,
        "rerank_timeout_seconds": 2.0,
    }
    values.update(overrides)
    return Settings.model_validate(values)


def _response(results: list[dict[str, object]]) -> httpx.Response:
    return httpx.Response(200, json={"results": results})


async def test_remote_reranker_sends_contract_and_sorts_results() -> None:
    client = FakeClient(
        response=_response(
            [
                {"index": 2, "score": 0.97},
                {"index": 0, "score": 0.8},
            ],
        ),
    )
    reranker = RemoteReranker(_settings(), client=client)

    results = await reranker.rerank(
        "consulta",
        ("documento a", "documento b", "documento c"),
        top_n=4,
    )

    assert [item.index for item in results] == [2, 0]
    assert [item.score for item in results] == [0.97, 0.8]
    assert client.method == "POST"
    assert client.url == "http://localhost:9999/rerank"
    assert client.headers["Authorization"] == "Bearer secret"
    assert client.allow_internal is True
    assert client.payload == {
        "model": "remote-reranker",
        "query": "consulta",
        "documents": ["documento a", "documento b", "documento c"],
        "top_n": 3,
        "max_length": 128,
    }
    assert reranker.status.backend == "remote"
    assert reranker.status.loaded is True


def test_remote_reranker_reports_missing_configuration() -> None:
    reranker = RemoteReranker(
        _settings(reranker_remote_url=""),
        client=FakeClient(),
    )

    assert reranker.status.loaded is False
    assert reranker.status.error == "remote_not_configured"


async def test_remote_reranker_requires_configuration_before_request() -> None:
    reranker = RemoteReranker(
        _settings(reranker_remote_url=""),
        client=FakeClient(),
    )

    with pytest.raises(RetrievalUnavailableError):
        await reranker.rerank("consulta", ("documento",))


async def test_remote_reranker_handles_empty_documents_without_request() -> None:
    client = FakeClient()
    reranker = RemoteReranker(_settings(), client=client)

    assert await reranker.rerank("consulta", ()) == ()
    assert client.payload == {}


async def test_remote_reranker_rejects_http_errors() -> None:
    reranker = RemoteReranker(
        _settings(),
        client=FakeClient(response=httpx.Response(503, content=b"unavailable")),
    )

    with pytest.raises(RetrievalUnavailableError):
        await reranker.rerank("consulta", ("documento",))


async def test_remote_reranker_rejects_invalid_payloads() -> None:
    cases = (
        httpx.Response(200, content=b"not json"),
        _response([{"index": 9, "score": 0.9}]),
        _response([{"index": 0, "score": 1.5}]),
        _response([{"index": 0, "score": 0.9}, {"index": 0, "score": 0.8}]),
    )

    for response in cases:
        reranker = RemoteReranker(_settings(), client=FakeClient(response=response))
        with pytest.raises(RetrievalUnavailableError):
            await reranker.rerank("consulta", ("documento",))


async def test_remote_reranker_maps_timeout() -> None:
    reranker = RemoteReranker(
        _settings(),
        client=FakeClient(error=httpx.ReadTimeout("timeout")),
    )

    with pytest.raises(RerankTimeoutError):
        await reranker.rerank("consulta", ("documento",))


async def test_remote_reranker_validates_query_and_top_n() -> None:
    reranker = RemoteReranker(_settings(), client=FakeClient())

    with pytest.raises(ValueError):
        await reranker.rerank(" ", ("documento",))
    with pytest.raises(ValueError):
        await reranker.rerank("consulta", ("documento",), top_n=0)
