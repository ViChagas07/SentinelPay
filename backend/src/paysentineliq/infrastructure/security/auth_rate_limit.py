from dataclasses import dataclass
from typing import Literal

from redis.asyncio import Redis

from paysentineliq.infrastructure.security.rate_limit import (
    RateLimitResult,
    TokenBucketRateLimiter,
)

AuthRateLimitScope = Literal["login", "register", "forgot", "resend"]


@dataclass(frozen=True, slots=True)
class AuthRateLimitSpec:
    scope: AuthRateLimitScope
    window_seconds: int
    ip_capacity: int
    identifier_capacity: int


class AuthRateLimiter:
    def __init__(
        self,
        redis: Redis,
        *,
        hash_secret: str,
        specs: tuple[AuthRateLimitSpec, ...],
    ) -> None:
        self._limiters: dict[tuple[str, str], TokenBucketRateLimiter] = {}
        for spec in specs:
            self._limiters[(spec.scope, "ip")] = TokenBucketRateLimiter(
                redis,
                capacity=spec.ip_capacity,
                refill_per_second=spec.ip_capacity / spec.window_seconds,
                hash_secret=hash_secret,
            )
            self._limiters[(spec.scope, "identifier")] = TokenBucketRateLimiter(
                redis,
                capacity=spec.identifier_capacity,
                refill_per_second=spec.identifier_capacity / spec.window_seconds,
                hash_secret=hash_secret,
            )

    async def consume(
        self,
        scope: AuthRateLimitScope,
        *,
        ip: str,
        identifier: str | None,
    ) -> RateLimitResult:
        ip_result = await self._limiters[(scope, "ip")].consume(f"{scope}:ip:{ip}")
        if not ip_result.allowed:
            return ip_result

        if not identifier:
            return ip_result

        identifier_result = await self._limiters[(scope, "identifier")].consume(
            f"{scope}:identifier:{identifier}",
        )
        if not identifier_result.allowed:
            return identifier_result

        return RateLimitResult(
            allowed=True,
            remaining=min(
                value
                for value in (ip_result.remaining, identifier_result.remaining)
                if value is not None
            ),
            retry_after_seconds=0,
            degraded=ip_result.degraded or identifier_result.degraded,
        )
