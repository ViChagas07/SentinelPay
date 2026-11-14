import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from paysentineliq.infrastructure.security.bruteforce import BruteForceService

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_bruteforce_blocks_by_ip_and_identifier_and_resets() -> None:
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    service = BruteForceService(
        redis,
        max_attempts=5,
        window_seconds=60,
        base_block_seconds=10,
        max_block_seconds=100,
        hash_secret="test-secret",
    )
    identifier = f"demo-{uuid4()}@example.com"
    ip = f"203.0.113.{uuid4().int % 250}"

    try:
        for _ in range(4):
            status = await service.record_failure(identifier=identifier, ip=ip)
            assert status.blocked is False

        blocked = await service.record_failure(identifier=identifier, ip=ip)
        assert blocked.blocked is True
        assert blocked.retry_after_seconds >= 10
        assert blocked.failures >= 5

        checked = await service.check(identifier=identifier, ip=ip)
        assert checked.blocked is True

        await service.reset(identifier=identifier, ip=ip)
        cleared = await service.check(identifier=identifier, ip=ip)
        assert cleared.blocked is False
        assert cleared.failures == 0
    finally:
        await service.reset(identifier=identifier, ip=ip)
        await redis.aclose()
