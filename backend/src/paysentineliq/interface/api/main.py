from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from paysentineliq.infrastructure.cache.swr import SWRCache
from paysentineliq.infrastructure.config import Settings, get_settings
from paysentineliq.infrastructure.db.engine import build_engine, build_session_factory
from paysentineliq.infrastructure.logging import configure_logging
from paysentineliq.infrastructure.security.bruteforce import BruteForceService
from paysentineliq.infrastructure.security.rate_limit import TokenBucketRateLimiter
from paysentineliq.interface.api.constants import API_V1_PREFIX, REQUEST_ID_HEADER
from paysentineliq.interface.api.limits import MaxBodySizeMiddleware, TimeoutMiddleware
from paysentineliq.interface.api.middleware import RequestIdMiddleware
from paysentineliq.interface.api.problems import register_exception_handlers
from paysentineliq.interface.api.rate_limit import RateLimitMiddleware
from paysentineliq.interface.api.routes.example import router as example_router
from paysentineliq.interface.api.routes.ops import router as ops_router
from paysentineliq.interface.api.security_headers import SecurityHeadersMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(resolved_settings)
        redis = Redis.from_url(
            resolved_settings.redis_url,
            decode_responses=True,
        )
        application.state.engine = engine
        application.state.session_factory = build_session_factory(engine)
        application.state.redis = redis
        application.state.rate_limiter = TokenBucketRateLimiter(
            redis,
            capacity=resolved_settings.rate_limit_capacity,
            refill_per_second=resolved_settings.rate_limit_refill_per_sec,
            hash_secret=resolved_settings.security_hash_secret,
        )
        application.state.swr_cache = SWRCache(
            redis,
            soft_ttl_seconds=resolved_settings.swr_soft_ttl_seconds,
            hard_ttl_seconds=resolved_settings.swr_hard_ttl_seconds,
            jitter_ratio=resolved_settings.swr_jitter_ratio,
            lock_ttl_seconds=resolved_settings.swr_lock_ttl_seconds,
            wait_timeout_seconds=resolved_settings.swr_wait_timeout_seconds,
        )
        application.state.brute_force = BruteForceService(
            redis,
            max_attempts=resolved_settings.bruteforce_max_attempts,
            window_seconds=resolved_settings.bruteforce_window_seconds,
            base_block_seconds=resolved_settings.bruteforce_base_block_seconds,
            max_block_seconds=resolved_settings.bruteforce_max_block_seconds,
            hash_secret=resolved_settings.security_hash_secret,
        )
        try:
            yield
        finally:
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(title="PaySentinelIQ", version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        MaxBodySizeMiddleware,
        max_bytes=resolved_settings.max_request_body_bytes,
    )
    app.add_middleware(
        TimeoutMiddleware,
        timeout_seconds=resolved_settings.request_timeout_seconds,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=resolved_settings.allowed_hosts_list,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept-Language",
            "X-Request-ID",
            "Idempotency-Key",
            "X-CSRF-Token",
        ],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=resolved_settings.app_env != "local",
    )
    register_exception_handlers(app)
    app.include_router(ops_router)
    app.include_router(example_router, prefix=API_V1_PREFIX)
    return app


app = create_app()
