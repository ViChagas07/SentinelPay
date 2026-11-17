import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from paysentineliq.domain.ports.retrieval import SparseVector
from paysentineliq.infrastructure.cache.embedding_cache import CachedEmbedder

pytestmark = [pytest.mark.integration, pytest.mark.docker]


class FakeEmbedder:
    dimension = 4
    model_id = "fake/it-cache"

    def __init__(self) -> None:
        self.dense_calls = 0
        self.sparse_calls = 0

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.dense_calls += 1
        return tuple((1.0, 0.0, 0.0, 0.0) for _ in texts)

    async def embed_sparse(self, texts: tuple[str, ...]) -> tuple[SparseVector, ...]:
        self.sparse_calls += 1
        return tuple(SparseVector(((7, 1.0),)) for _ in texts)


async def test_cached_embedder_uses_real_redis_and_ttl() -> None:
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    namespace = f"it-cache-{uuid4().hex}"
    embedder = FakeEmbedder()
    cached = CachedEmbedder(
        embedder,
        embedder,
        redis,
        ttl_seconds=60,
        namespace=namespace,
    )
    try:
        first = await cached.embed(("consulta",))
        second = await cached.embed(("consulta",))
        sparse_first = await cached.embed_sparse(("consulta",))
        sparse_second = await cached.embed_sparse(("consulta",))

        assert first == second
        assert sparse_first == sparse_second
        assert embedder.dense_calls == 1
        assert embedder.sparse_calls == 1
        keys = await redis.keys(f"{namespace}:*")
        ttls = [await redis.ttl(key) for key in keys]
        assert len(keys) == 2
        assert all(0 < ttl <= 60 for ttl in ttls)
    finally:
        keys = await redis.keys(f"{namespace}:*")
        if keys:
            await redis.delete(*keys)
        await redis.aclose()
