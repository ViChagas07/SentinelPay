import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from redis.asyncio import Redis
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from paysentineliq.infrastructure.cache.swr import SWRCache
from paysentineliq.infrastructure.config import Settings, get_settings
from paysentineliq.infrastructure.db.engine import build_engine, build_session_factory
from paysentineliq.infrastructure.logging import configure_logging
from paysentineliq.infrastructure.observability.metrics import (
    PlatformMetrics,
    set_platform_metrics,
)
from paysentineliq.infrastructure.observability.queue_depth import (
    QueueDepthMonitor,
    RabbitMqQueueDepthProvider,
)
from paysentineliq.infrastructure.observability.tracing import (
    configure_tracing,
    instrument_fastapi_app,
    instrument_sqlalchemy_engine,
)
from paysentineliq.infrastructure.security.bruteforce import BruteForceService
from paysentineliq.infrastructure.security.google_oidc import GoogleOIDCClient
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService
from paysentineliq.infrastructure.security.oidc_state import RedisOIDCStateStore
from paysentineliq.infrastructure.security.rate_limit import TokenBucketRateLimiter
from paysentineliq.infrastructure.security.revoked_tokens import (
    RedisRevokedTokenStore,
)
from paysentineliq.infrastructure.security.ssrf import SafeHttpClient, SSRFGuard
from paysentineliq.infrastructure.storage.inspector import (
    PdfImageDocumentInspector,
)
from paysentineliq.infrastructure.storage.s3 import S3StorageAdapter
from paysentineliq.interface.api.auth_context import AuthContextMiddleware
from paysentineliq.interface.api.constants import API_V1_PREFIX, REQUEST_ID_HEADER
from paysentineliq.interface.api.limits import MaxBodySizeMiddleware, TimeoutMiddleware
from paysentineliq.interface.api.middleware import RequestIdMiddleware
from paysentineliq.interface.api.problems import register_exception_handlers
from paysentineliq.interface.api.rate_limit import RateLimitMiddleware
from paysentineliq.interface.api.routes.analyses import router as analyses_router
from paysentineliq.interface.api.routes.auth import router as auth_router
from paysentineliq.interface.api.routes.documents import router as documents_router
from paysentineliq.interface.api.routes.example import router as example_router
from paysentineliq.interface.api.routes.notifications import (
    preferences_router as notification_preferences_router,
)
from paysentineliq.interface.api.routes.notifications import router as notifications_router
from paysentineliq.interface.api.routes.ops import router as ops_router
from paysentineliq.interface.api.routes.payables import router as payables_router
from paysentineliq.interface.api.routes.protected import router as protected_router
from paysentineliq.interface.api.routes.users import router as users_router
from paysentineliq.interface.api.security_headers import SecurityHeadersMiddleware
from paysentineliq.interface.api.upload_limit import UploadSizeLimitMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)
    configure_tracing(resolved_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(resolved_settings)
        instrument_sqlalchemy_engine(engine.sync_engine)
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
            metrics=metrics,
        )
        application.state.brute_force = BruteForceService(
            redis,
            max_attempts=resolved_settings.bruteforce_max_attempts,
            window_seconds=resolved_settings.bruteforce_window_seconds,
            base_block_seconds=resolved_settings.bruteforce_base_block_seconds,
            max_block_seconds=resolved_settings.bruteforce_max_block_seconds,
            hash_secret=resolved_settings.security_hash_secret,
        )
        application.state.token_service = JwtAccessTokenService(
            secret=resolved_settings.jwt_secret,
            ttl_minutes=resolved_settings.access_token_ttl_minutes,
        )
        application.state.revoked_tokens = RedisRevokedTokenStore(redis)
        application.state.oidc_state_store = RedisOIDCStateStore(redis)
        application.state.oidc_client = GoogleOIDCClient(
            client_id=resolved_settings.google_client_id,
            client_secret=resolved_settings.google_client_secret,
            redirect_uri=resolved_settings.google_redirect_uri,
            authorization_endpoint=resolved_settings.google_authorization_endpoint,
            token_endpoint=resolved_settings.google_token_endpoint,
            jwks_uri=resolved_settings.google_jwks_uri,
            issuer=resolved_settings.google_issuer,
        )
        application.state.document_inspector = PdfImageDocumentInspector()
        if resolved_settings.s3_configured:
            storage = S3StorageAdapter(
                resolved_settings,
                create_bucket_if_missing=(resolved_settings.app_env == "local"),
            )
            if resolved_settings.app_env == "local":
                await storage.ensure_bucket()
            application.state.storage = storage
        else:
            application.state.storage = None
        application.state.ssrf_guard = SSRFGuard(
            require_https=resolved_settings.app_env != "local",
            allowed_hosts=set(resolved_settings.ssrf_allowed_hosts_list),
        )
        application.state.safe_http_client = SafeHttpClient(application.state.ssrf_guard)
        rabbitmq_user, rabbitmq_password = resolved_settings.rabbitmq_management_credentials
        queue_monitor = QueueDepthMonitor(
            RabbitMqQueueDepthProvider(
                base_url=resolved_settings.rabbitmq_management_endpoint,
                username=rabbitmq_user,
                password=rabbitmq_password,
            ),
            metrics,
            interval_seconds=resolved_settings.queue_depth_refresh_seconds,
        )
        queue_monitor_task = asyncio.create_task(queue_monitor.run())
        try:
            yield
        finally:
            queue_monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await queue_monitor_task
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(
        title="PaySentinelIQ",
        version="0.1.0",
        lifespan=lifespan,
        debug=False,
        docs_url="/docs" if resolved_settings.app_env == "local" else None,
        redoc_url="/redoc" if resolved_settings.app_env == "local" else None,
        openapi_url=("/openapi.json" if resolved_settings.app_env == "local" else None),
    )
    app.state.settings = resolved_settings
    metrics = PlatformMetrics()
    app.state.metrics = metrics
    set_platform_metrics(metrics)
    instrument_fastapi_app(app, resolved_settings)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthContextMiddleware)
    app.add_middleware(
        MaxBodySizeMiddleware,
        max_bytes=resolved_settings.max_request_body_bytes,
        skip_paths=frozenset({"/api/v1/documents/upload", "/api/v1/analyses"}),
    )
    app.add_middleware(
        UploadSizeLimitMiddleware,
        paths=frozenset({"/api/v1/documents/upload", "/api/v1/analyses"}),
        max_bytes=resolved_settings.upload_max_mb * 1024 * 1024,
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
    app.include_router(auth_router, prefix=API_V1_PREFIX)
    app.include_router(users_router, prefix=API_V1_PREFIX)
    app.include_router(protected_router, prefix=API_V1_PREFIX)
    app.include_router(documents_router, prefix=API_V1_PREFIX)
    app.include_router(analyses_router, prefix=API_V1_PREFIX)
    app.include_router(payables_router, prefix=API_V1_PREFIX)
    app.include_router(notifications_router, prefix=API_V1_PREFIX)
    app.include_router(notification_preferences_router, prefix=API_V1_PREFIX)
    app.include_router(example_router, prefix=API_V1_PREFIX)
    return app


app = create_app()
