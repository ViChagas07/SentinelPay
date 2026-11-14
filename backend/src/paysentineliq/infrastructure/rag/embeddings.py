import asyncio
from collections.abc import Iterable

import httpx

from paysentineliq.application.errors import (
    EmbeddingDimensionError,
    EmbeddingUnavailableError,
)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _batches(texts: tuple[str, ...], size: int) -> Iterable[tuple[str, ...]]:
    for start in range(0, len(texts), size):
        yield texts[start : start + size]


class OpenAICompatibleEmbedding:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        dimension: int,
        api_key: str = "",
        timeout_seconds: float = 30.0,
        batch_size: int = 32,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("base_url is required")
        if not model.strip():
            raise ValueError("model is required")
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative")

        self._model = model
        self._dimension = dimension
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/",
            headers=headers,
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        vectors: list[tuple[float, ...]] = []
        for batch in _batches(texts, self._batch_size):
            vectors.extend(await self._embed_batch(batch))
        return tuple(vectors)

    async def _embed_batch(self, batch: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        payload = {"model": self._model, "input": list(batch)}
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post("embeddings", json=payload)
                if response.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                    await self._sleep(attempt)
                    continue
                if response.status_code >= 400:
                    raise EmbeddingUnavailableError("embedding endpoint returned an error")
                return self._parse(response, expected=len(batch))
            except httpx.TransportError as exc:
                if attempt >= self._max_retries:
                    raise EmbeddingUnavailableError(
                        "embedding endpoint is unavailable",
                    ) from exc
                await self._sleep(attempt)
        raise EmbeddingUnavailableError("embedding endpoint is unavailable")

    async def _sleep(self, attempt: int) -> None:
        if self._backoff_seconds:
            await asyncio.sleep(self._backoff_seconds * (2**attempt))

    def _parse(
        self,
        response: httpx.Response,
        *,
        expected: int,
    ) -> tuple[tuple[float, ...], ...]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise EmbeddingUnavailableError("invalid embedding response") from exc
        if not isinstance(payload, dict):
            raise EmbeddingUnavailableError("invalid embedding response")
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != expected:
            raise EmbeddingUnavailableError("embedding response has the wrong size")
        vectors: list[tuple[float, ...]] = []
        for item in data:
            if not isinstance(item, dict):
                raise EmbeddingUnavailableError("invalid embedding item")
            embedding = item.get("embedding")
            if not isinstance(embedding, list) or not all(
                isinstance(value, int | float) for value in embedding
            ):
                raise EmbeddingUnavailableError("invalid embedding vector")
            if len(embedding) != self._dimension:
                raise EmbeddingDimensionError(
                    "embedding dimension does not match EMBEDDING_DIM",
                )
            vectors.append(tuple(float(value) for value in embedding))
        return tuple(vectors)

    async def aclose(self) -> None:
        await self._client.aclose()
