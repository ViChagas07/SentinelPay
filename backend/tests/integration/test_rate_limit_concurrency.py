import asyncio
import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from paysentineliq.infrastructure.security.rate_limit import TokenBucketRateLimiter

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_token_bucket_is_atomic_under_concurrency() -> None:
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    identity = f"test:{uuid4()}"
    limiter = TokenBucketRateLimiter(
        redis,
        capacity=5,
        refill_per_second=0.0001,
        hash_secret="test-secret",
    )

    try:
        results = await asyncio.gather(*[limiter.consume(identity) for _ in range(20)])
        allowed = sum(1 for result in results if result.allowed)

        assert allowed == 5
        assert all(result.degraded is False for result in results)
        assert max(result.retry_after_seconds for result in results) > 0
    finally:
        await redis.delete(limiter.redis_key(identity))
        await redis.aclose()
