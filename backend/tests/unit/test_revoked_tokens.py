from typing import cast

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from paysentineliq.application.errors import SecurityServiceUnavailableError
from paysentineliq.infrastructure.security.revoked_tokens import (
    RedisRevokedTokenStore,
)

pytestmark = pytest.mark.unit


class FailingRedis:
    async def set(self, *args: object, **kwargs: object) -> object:
        raise RedisError("redis down")

    async def exists(self, *args: object, **kwargs: object) -> object:
        raise RedisError("redis down")


async def test_revoked_store_fails_closed_when_redis_is_down() -> None:
    store = RedisRevokedTokenStore(cast(Redis, FailingRedis()))

    with pytest.raises(SecurityServiceUnavailableError):
        await store.is_revoked("test-jti")

    with pytest.raises(SecurityServiceUnavailableError):
        await store.revoke("test-jti", 9999999999)
