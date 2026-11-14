import json
import math
from typing import Any

import httpx
import pytest

from paysentineliq.application.errors import (
    EmbeddingDimensionError,
    EmbeddingUnavailableError,
)
from paysentineliq.infrastructure.rag.embeddings import OpenAICompatibleEmbedding
from paysentineliq.infrastructure.rag.fake_embedding import (
    DeterministicHashEmbedding,
)

pytestmark = pytest.mark.unit


def _embedding_response(request: httpx.Request, dimension: int = 3) -> httpx.Response:
    payload = json.loads(request.content)
    vectors = [
        {"embedding": [float(index + 1), 0.0, 0.0][:dimension]}
        for index, _ in enumerate(payload["input"])
    ]
    return httpx.Response(200, json={"data": vectors})


async def test_batches_requests_and_returns_vectors() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        payload = json.loads(request.content)
        calls.append(payload)
        return _embedding_response(request)

    embedder = OpenAICompatibleEmbedding(
        base_url="http://embedding.test/v1",
        model="test-embedding",
        dimension=3,
        batch_size=2,
        backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    vectors = await embedder.embed(("a", "b", "c", "d", "e"))
    await embedder.aclose()

    assert len(vectors) == 5
    assert [len(call["input"]) for call in calls] == [2, 2, 1]
    assert all(len(vector) == 3 for vector in vectors)


async def test_retries_retryable_status_and_timeout() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503)
        return _embedding_response(request)

    embedder = OpenAICompatibleEmbedding(
        base_url="http://embedding.test/v1",
        model="test-embedding",
        dimension=3,
        max_retries=1,
        backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    vectors = await embedder.embed(("a",))
    await embedder.aclose()

    assert attempts == 2
    assert len(vectors) == 1


async def test_exhausted_retries_raise_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    embedder = OpenAICompatibleEmbedding(
        base_url="http://embedding.test/v1",
        model="test-embedding",
        dimension=3,
        max_retries=1,
        backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmbeddingUnavailableError):
        await embedder.embed(("a",))
    await embedder.aclose()


async def test_timeout_raises_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    embedder = OpenAICompatibleEmbedding(
        base_url="http://embedding.test/v1",
        model="test-embedding",
        dimension=3,
        max_retries=0,
        backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmbeddingUnavailableError):
        await embedder.embed(("a",))
    await embedder.aclose()


async def test_dimension_mismatch_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _embedding_response(request, dimension=2)

    embedder = OpenAICompatibleEmbedding(
        base_url="http://embedding.test/v1",
        model="test-embedding",
        dimension=3,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmbeddingDimensionError):
        await embedder.embed(("a",))
    await embedder.aclose()


async def test_empty_input_does_not_call_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not be called")

    embedder = OpenAICompatibleEmbedding(
        base_url="http://embedding.test/v1",
        model="test-embedding",
        dimension=3,
        transport=httpx.MockTransport(handler),
    )

    assert await embedder.embed(()) == ()
    await embedder.aclose()


async def test_deterministic_fake_embedding_is_normalized_and_stable() -> None:
    embedder = DeterministicHashEmbedding(dimension=8)

    first = await embedder.embed(("abc", "def"))
    second = await embedder.embed(("abc", "def"))

    assert first == second
    assert len(first[0]) == 8
    assert math.isclose(sum(value * value for value in first[0]), 1.0, rel_tol=1e-9)
    assert first[0] != first[1]
