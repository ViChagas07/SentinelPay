import os
import time
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from paysentineliq.infrastructure.security.revoked_tokens import (
    RedisRevokedTokenStore,
)

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_revoked_jti_is_stored_until_expiration() -> None:
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    store = RedisRevokedTokenStore(redis)
    jti = f"test-{uuid4()}"
    expires_at = int(time.time()) + 60

    try:
        await store.revoke(jti, expires_at)

        assert await store.is_revoked(jti) is True
        ttl = await redis.ttl(store.redis_key(jti))
        assert 0 < ttl <= 60
    finally:
        await redis.delete(store.redis_key(jti))
        await redis.aclose()
