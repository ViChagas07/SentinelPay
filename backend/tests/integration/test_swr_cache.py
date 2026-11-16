import asyncio
import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from paysentineliq.infrastructure.cache.swr import SWRCache
from paysentineliq.infrastructure.observability.metrics import PlatformMetrics

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_stale_while_revalidate_recomputes_once() -> None:
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    metrics = PlatformMetrics(multiprocess=False)
    cache = SWRCache(
        redis,
        soft_ttl_seconds=1,
        hard_ttl_seconds=10,
        jitter_ratio=0.0,
        lock_ttl_seconds=5,
        wait_timeout_seconds=1.0,
        metrics=metrics,
    )
    logical_key = f"test:{uuid4()}"
    calls = 0

    async def factory() -> str:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return f"value-{calls}"

    def encode(value: str) -> str:
        return value

    def decode(value: str) -> str:
        return value

    try:
        first = await cache.get_or_compute(logical_key, factory, encoder=encode, decoder=decode)
        assert first == "value-1"
        assert calls == 1

        hit = await cache.get_or_compute(logical_key, factory, encoder=encode, decoder=decode)
        assert hit == "value-1"
        assert calls == 1
        rendered = metrics.render().decode("utf-8")
        assert 'result="miss"' in rendered
        assert 'result="hit"' in rendered

        await asyncio.sleep(1.1)

        results = await asyncio.gather(
            *[
                cache.get_or_compute(logical_key, factory, encoder=encode, decoder=decode)
                for _ in range(20)
            ]
        )

        assert calls == 2
        assert all(result in {"value-1", "value-2"} for result in results)
        rendered = metrics.render().decode("utf-8")
        assert 'result="refresh"' in rendered
    finally:
        await redis.delete(*cache.redis_keys(logical_key))
        await redis.aclose()


async def test_cold_miss_stampede_computes_once() -> None:
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    metrics = PlatformMetrics(multiprocess=False)
    cache = SWRCache(
        redis,
        soft_ttl_seconds=10,
        hard_ttl_seconds=20,
        jitter_ratio=0.0,
        lock_ttl_seconds=5,
        wait_timeout_seconds=2.0,
        metrics=metrics,
    )
    logical_key = f"test:{uuid4()}"
    calls = 0

    async def factory() -> str:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.1)
        return f"value-{calls}"

    def encode(value: str) -> str:
        return value

    def decode(value: str) -> str:
        return value

    try:
        results = await asyncio.gather(
            *[
                cache.get_or_compute(logical_key, factory, encoder=encode, decoder=decode)
                for _ in range(30)
            ],
        )

        assert calls == 1
        assert results == ["value-1"] * 30
        rendered = metrics.render().decode("utf-8")
        assert 'result="miss"' in rendered
    finally:
        await redis.delete(*cache.redis_keys(logical_key))
        await redis.aclose()
