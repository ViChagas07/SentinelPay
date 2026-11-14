import hashlib
import hmac
import logging
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError

from paysentineliq.application.errors import SecurityServiceUnavailableError

_logger = logging.getLogger("paysentineliq")

_INCR_WITH_TTL_SCRIPT = """
local value = redis.call("INCR", KEYS[1])
if value == 1 then
  redis.call("EXPIRE", KEYS[1], ARGV[1])
end
return value
"""


@dataclass(frozen=True, slots=True)
class BruteForceStatus:
    blocked: bool
    retry_after_seconds: int
    failures: int


class BruteForceService:
    def __init__(
        self,
        redis: Redis,
        *,
        max_attempts: int,
        window_seconds: int,
        base_block_seconds: int,
        max_block_seconds: int,
        hash_secret: str,
    ) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if base_block_seconds <= 0:
            raise ValueError("base_block_seconds must be positive")
        if max_block_seconds < base_block_seconds:
            raise ValueError("max_block_seconds must be >= base_block_seconds")

        self._redis = redis
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._base_block_seconds = base_block_seconds
        self._max_block_seconds = max_block_seconds
        self._hash_secret = hash_secret.encode("utf-8")

    def _key(self, scope: str, value: str) -> str:
        digest = hmac.new(
            self._hash_secret,
            f"{scope}:{value}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"bf:{scope}:{digest}"

    def _keys(self, *, identifier: str, ip: str) -> list[str]:
        return [
            self._key("ip-attempts", ip),
            self._key("id-attempts", identifier),
            self._key("ip-block", ip),
            self._key("id-block", identifier),
        ]

    async def check(self, *, identifier: str, ip: str) -> BruteForceStatus:
        try:
            ip_block_ttl = await self._redis.ttl(self._key("ip-block", ip))
            identifier_block_ttl = await self._redis.ttl(self._key("id-block", identifier))
            ip_attempts = await self._redis.get(self._key("ip-attempts", ip))
            identifier_attempts = await self._redis.get(self._key("id-attempts", identifier))
        except RedisError as exc:
            _logger.error("bruteforce_redis_failure")
            raise SecurityServiceUnavailableError() from exc

        retry_after = max(ip_block_ttl, identifier_block_ttl, 0)
        failures = max(
            _to_int(ip_attempts),
            _to_int(identifier_attempts),
        )
        return BruteForceStatus(
            blocked=retry_after > 0,
            retry_after_seconds=retry_after,
            failures=failures,
        )

    async def record_failure(self, *, identifier: str, ip: str) -> BruteForceStatus:
        try:
            ip_attempts = int(
                await self._redis.eval(
                    _INCR_WITH_TTL_SCRIPT,
                    1,
                    self._key("ip-attempts", ip),
                    self._window_seconds,
                )
            )
            identifier_attempts = int(
                await self._redis.eval(
                    _INCR_WITH_TTL_SCRIPT,
                    1,
                    self._key("id-attempts", identifier),
                    self._window_seconds,
                )
            )

            for scope, attempts, value in (
                ("ip-block", ip_attempts, ip),
                ("id-block", identifier_attempts, identifier),
            ):
                if attempts >= self._max_attempts:
                    exponent = min(attempts - self._max_attempts, 16)
                    block_seconds = min(
                        self._base_block_seconds * (2**exponent),
                        self._max_block_seconds,
                    )
                    await self._redis.set(
                        self._key(scope, value),
                        "1",
                        ex=block_seconds,
                    )
        except RedisError as exc:
            _logger.error("bruteforce_redis_failure")
            raise SecurityServiceUnavailableError() from exc

        return await self.check(identifier=identifier, ip=ip)

    async def reset(self, *, identifier: str, ip: str) -> None:
        try:
            await self._redis.delete(*self._keys(identifier=identifier, ip=ip))
        except RedisError as exc:
            _logger.error("bruteforce_redis_failure")
            raise SecurityServiceUnavailableError() from exc


def _to_int(value: object) -> int:
    if value is None:
        return 0
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
