from typing import cast

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from paysentineliq.application.errors import SecurityServiceUnavailableError
from paysentineliq.infrastructure.security.bruteforce import BruteForceService

pytestmark = pytest.mark.unit


class FailingRedis:
    async def ttl(self, *args: object, **kwargs: object) -> object:
        raise RedisError("redis down")

    async def get(self, *args: object, **kwargs: object) -> object:
        raise RedisError("redis down")

    async def eval(self, *args: object, **kwargs: object) -> object:
        raise RedisError("redis down")

    async def set(self, *args: object, **kwargs: object) -> object:
        raise RedisError("redis down")

    async def delete(self, *args: object, **kwargs: object) -> object:
        raise RedisError("redis down")


async def test_bruteforce_fails_closed_when_redis_is_down() -> None:
    service = BruteForceService(
        cast(Redis, FailingRedis()),
        max_attempts=5,
        window_seconds=60,
        base_block_seconds=10,
        max_block_seconds=100,
        hash_secret="test-secret",
    )

    with pytest.raises(SecurityServiceUnavailableError):
        await service.check(identifier="demo@example.com", ip="203.0.113.10")
