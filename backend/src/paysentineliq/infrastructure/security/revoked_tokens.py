import logging
from datetime import UTC, datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError

from paysentineliq.application.errors import SecurityServiceUnavailableError

_logger = logging.getLogger("paysentineliq")


class RedisRevokedTokenStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def redis_key(self, jti: str) -> str:
        return f"revoked:jti:{jti}"

    async def revoke(self, jti: str, expires_at: int) -> None:
        ttl = max(1, expires_at - int(datetime.now(UTC).timestamp()))
        try:
            await self._redis.set(self.redis_key(jti), "1", ex=ttl)
        except RedisError as exc:
            _logger.error("revoked_token_store_failure")
            raise SecurityServiceUnavailableError() from exc

    async def is_revoked(self, jti: str) -> bool:
        try:
            return bool(await self._redis.exists(self.redis_key(jti)))
        except RedisError as exc:
            _logger.error("revoked_token_store_failure")
            raise SecurityServiceUnavailableError() from exc
