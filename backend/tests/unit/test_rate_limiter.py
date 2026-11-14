from typing import cast

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from paysentineliq.infrastructure.security.rate_limit import TokenBucketRateLimiter

pytestmark = pytest.mark.unit


class FailingRedis:
    async def eval(self, *args: object, **kwargs: object) -> object:
        raise RedisError("redis down")


async def test_rate_limiter_fails_open_when_redis_is_down() -> None:
    limiter = TokenBucketRateLimiter(
        cast(Redis, FailingRedis()),
        capacity=5,
        refill_per_second=1.0,
        hash_secret="test-secret",
    )

    result = await limiter.consume("ip:203.0.113.10")

    assert result.allowed is True
    assert result.degraded is True
    assert result.retry_after_seconds == 0
