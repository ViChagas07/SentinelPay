import hashlib
import logging
import secrets

from redis.asyncio import Redis
from redis.exceptions import RedisError

from paysentineliq.application.errors import SecurityServiceUnavailableError

_logger = logging.getLogger("paysentineliq")


class RedisLoginTicketStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def redis_key(self, ticket: str) -> str:
        digest = hashlib.sha256(ticket.encode("utf-8")).hexdigest()
        return f"auth:ticket:{digest}"

    async def issue(self, refresh_token: str, ttl_seconds: int) -> str:
        ticket = secrets.token_urlsafe(32)
        try:
            await self._redis.set(
                self.redis_key(ticket),
                refresh_token,
                ex=ttl_seconds,
            )
        except RedisError as exc:
            _logger.error("login_ticket_store_failure")
            raise SecurityServiceUnavailableError() from exc
        return ticket

    async def consume(self, ticket: str) -> str | None:
        try:
            raw = await self._redis.getdel(self.redis_key(ticket))
        except RedisError as exc:
            _logger.error("login_ticket_store_failure")
            raise SecurityServiceUnavailableError() from exc
        return raw if isinstance(raw, str) and raw else None
