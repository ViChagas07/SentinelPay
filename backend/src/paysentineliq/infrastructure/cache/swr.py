import asyncio
import hashlib
import logging
import random
import secrets
from collections.abc import Awaitable, Callable
from typing import TypeVar

from redis.asyncio import Redis
from redis.exceptions import RedisError

from paysentineliq.infrastructure.observability.metrics import (
    PlatformMetrics,
    get_platform_metrics,
)

_logger = logging.getLogger("paysentineliq")

T = TypeVar("T")

_RELEASE_LOCK_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
end
return 0
"""


class CacheMissError(RuntimeError):
    pass


class SWRCache:
    def __init__(
        self,
        redis: Redis,
        *,
        soft_ttl_seconds: int,
        hard_ttl_seconds: int,
        jitter_ratio: float,
        lock_ttl_seconds: int = 10,
        wait_timeout_seconds: float = 2.0,
        key_prefix: str = "swr",
        metrics: PlatformMetrics | None = None,
    ) -> None:
        if soft_ttl_seconds <= 0:
            raise ValueError("soft_ttl_seconds must be positive")
        if hard_ttl_seconds <= soft_ttl_seconds:
            raise ValueError("hard_ttl_seconds must be greater than soft_ttl_seconds")
        if not 0.0 <= jitter_ratio <= 1.0:
            raise ValueError("jitter_ratio must be between 0 and 1")
        if lock_ttl_seconds <= 0:
            raise ValueError("lock_ttl_seconds must be positive")
        if wait_timeout_seconds <= 0:
            raise ValueError("wait_timeout_seconds must be positive")

        self._redis = redis
        self._soft_ttl = soft_ttl_seconds
        self._hard_ttl = hard_ttl_seconds
        self._jitter = jitter_ratio
        self._lock_ttl = lock_ttl_seconds
        self._wait_timeout = wait_timeout_seconds
        self._prefix = key_prefix
        self._rng = random.SystemRandom()
        self._metrics = metrics if metrics is not None else get_platform_metrics()

    def redis_keys(self, key: str) -> tuple[str, str, str]:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        base = f"{self._prefix}:{digest}"
        return f"{base}:value", f"{base}:soft", f"{base}:lock"

    async def get_or_compute(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        *,
        encoder: Callable[[T], str],
        decoder: Callable[[str], T],
    ) -> T:
        try:
            return await self._get_or_compute(
                key,
                factory,
                encoder=encoder,
                decoder=decoder,
            )
        except RedisError:
            self._metrics.record_cache("error")
            raise

    async def _get_or_compute(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        *,
        encoder: Callable[[T], str],
        decoder: Callable[[str], T],
    ) -> T:
        value_key, soft_key, lock_key = self.redis_keys(key)
        cached = await self._redis.get(value_key)

        if cached is not None:
            soft_exists = await self._redis.exists(soft_key)
            if soft_exists:
                self._metrics.record_cache("hit")
                return decoder(_as_text(cached))

            token = secrets.token_urlsafe(16)
            acquired = await self._redis.set(lock_key, token, nx=True, ex=self._lock_ttl)
            if not acquired:
                self._metrics.record_cache("stale")
                return decoder(_as_text(cached))

            try:
                refreshed = await self._redis.get(value_key)
                if refreshed is not None and await self._redis.exists(soft_key):
                    self._metrics.record_cache("hit")
                    return decoder(_as_text(refreshed))
                value = await factory()
                await self._store(value_key, soft_key, encoder(value))
                self._metrics.record_cache("refresh")
                return value
            finally:
                await self._release(lock_key, token)

        self._metrics.record_cache("miss")
        token = secrets.token_urlsafe(16)
        acquired = await self._redis.set(lock_key, token, nx=True, ex=self._lock_ttl)
        if acquired:
            try:
                value = await factory()
                await self._store(value_key, soft_key, encoder(value))
                return value
            finally:
                await self._release(lock_key, token)

        deadline = asyncio.get_running_loop().time() + self._wait_timeout
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.05)
            cached = await self._redis.get(value_key)
            if cached is not None:
                return decoder(_as_text(cached))

        raise CacheMissError("cache fill timed out")

    async def _store(self, value_key: str, soft_key: str, encoded: str) -> None:
        soft_ttl, hard_ttl = self._ttls()
        await self._redis.set(value_key, encoded, ex=hard_ttl)
        await self._redis.set(soft_key, "1", ex=soft_ttl)

    def _ttls(self) -> tuple[int, int]:
        jitter = self._rng.uniform(1.0 - self._jitter, 1.0 + self._jitter)
        soft_ttl = max(1, int(self._soft_ttl * jitter))
        hard_ttl = max(soft_ttl + 1, int(self._hard_ttl * jitter))
        return soft_ttl, hard_ttl

    async def _release(self, lock_key: str, token: str) -> None:
        try:
            await self._redis.eval(_RELEASE_LOCK_SCRIPT, 1, lock_key, token)
        except RedisError:
            _logger.warning("swr_lock_release_failed")


def _as_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
