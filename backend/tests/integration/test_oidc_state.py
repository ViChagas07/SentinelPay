import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from paysentineliq.application.ports.oidc_state import OIDCState
from paysentineliq.infrastructure.security.oidc_state import RedisOIDCStateStore

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_oidc_state_is_one_time() -> None:
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    store = RedisOIDCStateStore(redis)
    state = f"state-{uuid4()}"
    data = OIDCState(
        nonce="nonce-value",
        code_verifier="verifier-value",
        redirect_uri="https://app.example/callback",
    )

    try:
        await store.save(state, data, ttl_seconds=60)

        ttl = await redis.ttl(store.redis_key(state))
        assert 0 < ttl <= 60
        assert await store.pop(state) == data
        assert await store.pop(state) is None
    finally:
        await redis.delete(store.redis_key(state))
        await redis.aclose()
