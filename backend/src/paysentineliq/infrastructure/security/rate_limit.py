import hashlib
import hmac
import logging
import math
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError

_logger = logging.getLogger("paysentineliq")

_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local clock = redis.call("TIME")
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000
local data = redis.call("HMGET", key, "tokens", "ts")
local tokens = tonumber(data[1])
local last = tonumber(data[2])
if tokens == nil then
  tokens = capacity
  last = now
end
local delta = math.max(0, now - last)
tokens = math.min(capacity, tokens + delta * refill)
local allowed = 0
local retry_after = 0
if tokens >= requested then
  tokens = tokens - requested
  allowed = 1
else
  retry_after = math.ceil((requested - tokens) / refill)
end
redis.call("HSET", key, "tokens", tokens, "ts", now)
redis.call("EXPIRE", key, ttl)
return {allowed, math.floor(tokens), retry_after}
"""


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    remaining: int | None
    retry_after_seconds: int
    degraded: bool = False


class RateLimiter(Protocol):
    async def consume(self, identity: str) -> RateLimitResult: ...


class TokenBucketRateLimiter:
    def __init__(
        self,
        redis: Redis,
        *,
        capacity: int,
        refill_per_second: float,
        hash_secret: str,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_per_second <= 0:
            raise ValueError("refill_per_second must be positive")

        self._redis = redis
        self._capacity = capacity
        self._refill_per_second = refill_per_second
        self._hash_secret = hash_secret.encode("utf-8")
        self._ttl_seconds = max(2, math.ceil(capacity / refill_per_second) + 1)

    def redis_key(self, identity: str) -> str:
        digest = hmac.new(
            self._hash_secret,
            identity.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"rl:{digest}"

    async def consume(self, identity: str) -> RateLimitResult:
        try:
            raw = await self._redis.eval(
                _TOKEN_BUCKET_SCRIPT,
                1,
                self.redis_key(identity),
                self._capacity,
                self._refill_per_second,
                self._ttl_seconds,
                1,
            )
        except (RedisError, TypeError, ValueError):
            _logger.warning("rate_limit_redis_failure")
            return RateLimitResult(
                allowed=True,
                remaining=None,
                retry_after_seconds=0,
                degraded=True,
            )

        try:
            if not isinstance(raw, (list, tuple)) or len(raw) != 3:
                raise ValueError("unexpected lua response")
            return RateLimitResult(
                allowed=bool(int(raw[0])),
                remaining=int(raw[1]),
                retry_after_seconds=max(0, int(raw[2])),
            )
        except (TypeError, ValueError):
            _logger.warning("rate_limit_redis_failure")
            return RateLimitResult(
                allowed=True,
                remaining=None,
                retry_after_seconds=0,
                degraded=True,
            )
