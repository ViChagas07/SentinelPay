import os

import pytest
from redis.asyncio import Redis

from paysentineliq.infrastructure.security.login_tickets import RedisLoginTicketStore

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_login_ticket_is_one_time_and_not_stored_in_the_key() -> None:
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    store = RedisLoginTicketStore(redis)

    try:
        ticket = await store.issue("refresh-token-value", ttl_seconds=60)
        key = store.redis_key(ticket)

        ttl = await redis.ttl(key)
        assert 0 < ttl <= 60
        assert ticket not in key
        assert await store.consume(ticket) == "refresh-token-value"
        assert await store.consume(ticket) is None
        assert await redis.exists(key) == 0
    finally:
        await redis.aclose()
