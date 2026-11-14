import asyncio
import json
import time
from collections.abc import Mapping
from typing import Protocol

import httpx
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from paysentineliq.application.errors import LlmUnavailableError, SSRFBlockedError
from paysentineliq.application.ports.llm import LlmMessage, LlmResponse
from paysentineliq.infrastructure.observability.metrics import (
    PlatformMetrics,
    get_platform_metrics,
)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class JsonHttpClientPort(Protocol):
    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        content: bytes | None = None,
        allow_internal: bool = False,
    ) -> httpx.Response: ...


class OpenAICompatibleLLM:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        temperature: float = 0.1,
        max_retries: int = 2,
        backoff_seconds: float = 1.0,
        timeout_seconds: float = 30.0,
        client: JsonHttpClientPort,
        metrics: PlatformMetrics | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("base_url is required")
        if not model.strip():
            raise ValueError("model is required")
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("temperature must be between 0 and 1")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._temperature = temperature
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._timeout_seconds = timeout_seconds
        self._client = client
        self._metrics = metrics if metrics is not None else get_platform_metrics()

    @property
    def model(self) -> str:
        return self._model

    async def complete(
        self,
        messages: tuple[LlmMessage, ...],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> LlmResponse:
        if not messages:
            raise ValueError("messages must not be empty")
        payload = {
            "model": self._model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        url = f"{self._base_url}/chat/completions"
        started = time.perf_counter()
        outcome = "error"
        tracer = trace.get_tracer("paysentineliq")
        with tracer.start_as_current_span("llm.complete") as span:
            span.set_attribute("llm.model", self._model)
            try:
                response = await self._request_with_retries(url, headers, payload, span)
                outcome = "success"
                return response
            except Exception:
                span.set_status(Status(StatusCode.ERROR))
                raise
            finally:
                self._metrics.record_llm(
                    self._model,
                    outcome,
                    time.perf_counter() - started,
                )
                span.set_attribute("llm.outcome", outcome)

    async def _request_with_retries(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        span: trace.Span,
    ) -> LlmResponse:
        for attempt in range(self._max_retries + 1):
            span.set_attribute("llm.retries", attempt)
            try:
                response = await self._client.request(
                    "POST",
                    url,
                    headers=headers,
                    content=json.dumps(payload).encode("utf-8"),
                    allow_internal=True,
                )
                if response.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                    self._metrics.record_llm(self._model, "retry")
                    await self._sleep(attempt)
                    continue
                if response.status_code >= 400:
                    raise LlmUnavailableError("LLM endpoint returned an error")
                content = self._content(response)
                return LlmResponse(content=content, model=self._model)
            except (httpx.TransportError, SSRFBlockedError) as exc:
                if attempt >= self._max_retries:
                    raise LlmUnavailableError("LLM endpoint is unavailable") from exc
                self._metrics.record_llm(self._model, "retry")
                await self._sleep(attempt)
        raise LlmUnavailableError("LLM endpoint is unavailable")

    async def _sleep(self, attempt: int) -> None:
        if self._backoff_seconds:
            await asyncio.sleep(self._backoff_seconds * (2**attempt))

    @staticmethod
    def _content(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError as exc:
            raise LlmUnavailableError("invalid LLM response") from exc
        try:
            choices = payload["choices"]
            content = choices[0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmUnavailableError("invalid LLM response") from exc
        if not isinstance(content, str) or not content.strip():
            raise LlmUnavailableError("empty LLM response")
        return content
