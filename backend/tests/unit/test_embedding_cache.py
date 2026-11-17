import json

import pytest

from paysentineliq.domain.ports.retrieval import SparseVector
from paysentineliq.infrastructure.cache.embedding_cache import CachedEmbedder

pytestmark = pytest.mark.unit


class FakeCache:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.reads = 0
        self.writes = 0
        self.fail_reads = False
        self.fail_writes = False

    async def mget(self, keys: object) -> list[str | None]:
        self.reads += 1
        if self.fail_reads:
            raise RuntimeError("redis offline")
        if not isinstance(keys, (list, tuple)):
            raise AssertionError("keys must be a sequence")
        return [self.data.get(str(key)) for key in keys]

    async def set(
        self,
        name: str,
        value: str,
        ex: int | None = None,
    ) -> bool:
        self.writes += 1
        if self.fail_writes:
            raise RuntimeError("redis offline")
        assert ex is not None and ex > 0
        self.data[name] = value
        return True


class FakeEmbedder:
    dimension = 3
    model_id = "fake/model"

    def __init__(self) -> None:
        self.dense_calls = 0
        self.sparse_calls = 0

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.dense_calls += 1
        return tuple((float(len(text)), 1.0, 2.0) for text in texts)

    async def embed_sparse(self, texts: tuple[str, ...]) -> tuple[SparseVector, ...]:
        self.sparse_calls += 1
        return tuple(SparseVector(((len(text) + 1, 1.0),)) for text in texts)


def _cached(
    *,
    cache: FakeCache | None = None,
) -> tuple[CachedEmbedder, FakeEmbedder, FakeCache]:
    cache = cache or FakeCache()
    embedder = FakeEmbedder()
    return (
        CachedEmbedder(
            embedder,
            embedder,
            cache,
            ttl_seconds=120,
        ),
        embedder,
        cache,
    )


async def test_dense_embedding_is_cached_after_first_call() -> None:
    cached, embedder, cache = _cached()

    first = await cached.embed(("segredo do cliente",))
    second = await cached.embed(("segredo do cliente",))

    assert first == second
    assert embedder.dense_calls == 1
    assert cache.reads == 2
    assert cache.writes == 1


async def test_cache_key_does_not_contain_raw_query_text() -> None:
    cached, _, cache = _cached()

    await cached.embed(("segredo do cliente",))

    key = next(iter(cache.data))
    assert "segredo" not in key
    assert "cliente" not in key
    assert len(key.rsplit(":", 1)[-1]) == 64


async def test_corrupted_dense_cache_is_treated_as_miss() -> None:
    cached, embedder, cache = _cached()
    text = "consulta"
    key = cached._key("dense", text)
    cache.data[key] = "{not json"

    result = await cached.embed((text,))

    assert len(result) == 1
    assert embedder.dense_calls == 1
    assert cache.data[key] != "{not json"


async def test_wrong_dimension_cache_is_treated_as_miss() -> None:
    cached, embedder, cache = _cached()
    text = "consulta"
    key = cached._key("dense", text)
    cache.data[key] = json.dumps([1.0])

    result = await cached.embed((text,))

    assert len(result[0]) == 3
    assert embedder.dense_calls == 1


async def test_sparse_embedding_is_cached_after_first_call() -> None:
    cached, embedder, cache = _cached()

    first = await cached.embed_sparse(("consulta",))
    second = await cached.embed_sparse(("consulta",))

    assert first == second
    assert embedder.sparse_calls == 1
    assert cache.writes == 1


async def test_embed_hybrid_caches_both_vectors() -> None:
    cached, embedder, _ = _cached()

    first = await cached.embed_hybrid(("consulta",))
    second = await cached.embed_hybrid(("consulta",))

    assert first == second
    assert embedder.dense_calls == 1
    assert embedder.sparse_calls == 1


async def test_cache_read_failure_falls_back_to_embedder() -> None:
    cached, embedder, cache = _cached()
    cache.fail_reads = True

    result = await cached.embed(("consulta",))

    assert len(result) == 1
    assert embedder.dense_calls == 1


async def test_cache_write_failure_does_not_break_embedding() -> None:
    cached, embedder, cache = _cached()
    cache.fail_writes = True

    result = await cached.embed(("consulta",))

    assert len(result) == 1
    assert embedder.dense_calls == 1


async def test_cache_requires_positive_ttl() -> None:
    embedder = FakeEmbedder()

    with pytest.raises(ValueError):
        CachedEmbedder(embedder, embedder, FakeCache(), ttl_seconds=0)
