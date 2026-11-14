import asyncio
import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from paysentineliq.infrastructure.cache.swr import SWRCache

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_stale_while_revalidate_recomputes_once() -> None:
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    cache = SWRCache(
        redis,
        soft_ttl_seconds=1,
        hard_ttl_seconds=10,
        jitter_ratio=0.0,
        lock_ttl_seconds=5,
        wait_timeout_seconds=1.0,
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

        await asyncio.sleep(1.1)

        results = await asyncio.gather(
            *[
                cache.get_or_compute(logical_key, factory, encoder=encode, decoder=decode)
                for _ in range(20)
            ]
        )

        assert calls == 2
        assert all(result in {"value-1", "value-2"} for result in results)
    finally:
        await redis.delete(*cache.redis_keys(logical_key))
        await redis.aclose()
