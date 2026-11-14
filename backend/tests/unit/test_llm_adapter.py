import json
from collections.abc import Mapping
from typing import Any

import httpx
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from paysentineliq.application.errors import LlmUnavailableError
from paysentineliq.application.ports.llm import LlmMessage
from paysentineliq.infrastructure.ai.llm import OpenAICompatibleLLM
from paysentineliq.infrastructure.observability.metrics import PlatformMetrics
from paysentineliq.infrastructure.observability.tracing import (
    PiiSanitizingSpanProcessor,
)

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


def _llm(
    client: FakeHttpClient,
    *,
    metrics: PlatformMetrics | None = None,
) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(
        base_url="http://llm.test/v1",
        model="local-model",
        api_key="secret",
        max_retries=1,
        backoff_seconds=0,
        client=client,
        metrics=metrics,
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


async def test_llm_records_retry_and_success_metrics() -> None:
    metrics = PlatformMetrics(multiprocess=False)
    client = FakeHttpClient([httpx.Response(503), _response("ok")])
    llm = _llm(client, metrics=metrics)

    await llm.complete((LlmMessage(role="user", content="hi"),))

    text = metrics.render().decode("utf-8")
    assert "paysentineliq_llm_requests_total{" in text
    assert 'outcome="retry"' in text
    assert 'outcome="success"' in text
    assert "paysentineliq_llm_request_duration_seconds_count{" in text


async def test_llm_records_error_metrics() -> None:
    metrics = PlatformMetrics(multiprocess=False)
    client = FakeHttpClient([httpx.Response(503), httpx.Response(503)])
    llm = _llm(client, metrics=metrics)

    with pytest.raises(LlmUnavailableError):
        await llm.complete((LlmMessage(role="user", content="hi"),))

    text = metrics.render().decode("utf-8")
    assert 'outcome="error"' in text


async def test_llm_span_never_contains_prompt_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(
        PiiSanitizingSpanProcessor(SimpleSpanProcessor(exporter)),
    )
    monkeypatch.setattr(trace, "get_tracer", provider.get_tracer)
    client = FakeHttpClient([_response("ok")])
    llm = _llm(client)

    await llm.complete(
        (
            LlmMessage(
                role="user",
                content="CPF 529.982.247-25 e email user@example.com",
            ),
        ),
    )

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    dumped = repr(dict(spans[0].attributes or {}))
    assert "529.982.247-25" not in dumped
    assert "user@example.com" not in dumped
    assert "CPF" not in dumped
    assert spans[0].name == "llm.complete"
