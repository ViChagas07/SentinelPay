import json
from collections.abc import Mapping
from typing import Any

import httpx
import pytest

from paysentineliq.application.errors import LlmUnavailableError
from paysentineliq.application.ports.llm import LlmMessage
from paysentineliq.infrastructure.ai.llm import OpenAICompatibleLLM

pytestmark = pytest.mark.unit


class FakeHttpClient:
    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        content: bytes | None = None,
        allow_internal: bool = False,
    ) -> httpx.Response:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "content": content,
                "allow_internal": allow_internal,
            },
        )
        if not self._responses:
            raise AssertionError("no fake HTTP response configured")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
    )


def _llm(client: FakeHttpClient) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(
        base_url="http://llm.test/v1",
        model="local-model",
        api_key="secret",
        max_retries=1,
        backoff_seconds=0,
        client=client,
    )


async def test_complete_sends_messages_and_returns_content() -> None:
    client = FakeHttpClient([_response("hello")])
    llm = _llm(client)

    result = await llm.complete((LlmMessage(role="user", content="hi"),))

    assert result.content == "hello"
    assert result.model == "local-model"
    call = client.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "http://llm.test/v1/chat/completions"
    assert call["allow_internal"] is True
    assert call["headers"]["Authorization"] == "Bearer secret"
    payload = json.loads(call["content"])
    assert payload["model"] == "local-model"
    assert payload["messages"] == [{"role": "user", "content": "hi"}]


async def test_retryable_status_is_retried() -> None:
    client = FakeHttpClient([httpx.Response(503), _response("ok")])
    llm = _llm(client)

    result = await llm.complete((LlmMessage(role="user", content="hi"),))

    assert result.content == "ok"
    assert len(client.calls) == 2


async def test_exhausted_retries_raise() -> None:
    client = FakeHttpClient([httpx.Response(503), httpx.Response(503)])
    llm = _llm(client)

    with pytest.raises(LlmUnavailableError):
        await llm.complete((LlmMessage(role="user", content="hi"),))


async def test_timeout_raises() -> None:
    client = FakeHttpClient(
        [httpx.TimeoutException("timeout"), httpx.TimeoutException("timeout")],
    )
    llm = _llm(client)

    with pytest.raises(LlmUnavailableError):
        await llm.complete((LlmMessage(role="user", content="hi"),))


async def test_invalid_json_response_raises() -> None:
    client = FakeHttpClient([httpx.Response(200, content=b"not json")])
    llm = _llm(client)

    with pytest.raises(LlmUnavailableError):
        await llm.complete((LlmMessage(role="user", content="hi"),))


async def test_empty_content_raises() -> None:
    client = FakeHttpClient([_response("")])
    llm = _llm(client)

    with pytest.raises(LlmUnavailableError):
        await llm.complete((LlmMessage(role="user", content="hi"),))
