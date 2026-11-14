import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from paysentineliq.infrastructure.security.rate_limit import RateLimiter
from paysentineliq.interface.api.constants import API_V1_PREFIX
from paysentineliq.interface.api.problems import build_problem_response

_logger = logging.getLogger("paysentineliq")
_AUTH_PREFIX = f"{API_V1_PREFIX}/auth"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if not path.startswith(API_V1_PREFIX) or request.method == "OPTIONS":
            return await call_next(request)

        limiter: RateLimiter | None = getattr(request.app.state, "rate_limiter", None)
        if limiter is None:
            return await call_next(request)

        is_auth = path.startswith(_AUTH_PREFIX)
        ip_response = await self._apply_limit(
            request,
            limiter,
            self._client_identity(request),
            scope="ip",
            is_auth=is_auth,
        )
        if ip_response is not None:
            return ip_response

        user_id = getattr(request.state, "user_id", None)
        if user_id is not None:
            user_response = await self._apply_limit(
                request,
                limiter,
                f"user:{user_id}",
                scope="user",
                is_auth=is_auth,
            )
            if user_response is not None:
                return user_response

        return await call_next(request)

    @staticmethod
    def _client_identity(request: Request) -> str:
        client = request.client
        return f"ip:{client.host}" if client is not None else "ip:unknown"

    async def _apply_limit(
        self,
        request: Request,
        limiter: RateLimiter,
        identity: str,
        *,
        scope: str,
        is_auth: bool,
    ) -> Response | None:
        result = await limiter.consume(identity)

        if result.degraded:
            if is_auth:
                _logger.warning(
                    "rate_limit_unavailable path=%s",
                    request.url.path,
                )
                return build_problem_response(
                    request,
                    status_code=503,
                    code="rate_limit_unavailable",
                    title="Service unavailable",
                    detail="Rate limiting is unavailable.",
                    extra_headers={"Retry-After": "1"},
                )
            return None

        if result.allowed:
            return None

        retry_after = max(1, result.retry_after_seconds)
        metrics = getattr(request.app.state, "metrics", None)
        if metrics is not None:
            metrics.record_rate_limit(scope)
        _logger.warning(
            "rate_limited scope=%s retry_after=%s",
            scope,
            retry_after,
        )
        return build_problem_response(
            request,
            status_code=429,
            code="rate_limited",
            title="Too many requests",
            detail="Rate limit exceeded.",
            extra_headers={"Retry-After": str(retry_after)},
        )
