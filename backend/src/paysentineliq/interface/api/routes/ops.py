import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from paysentineliq.application.ports.readiness import ReadinessChecker
from paysentineliq.infrastructure.observability.metrics import PlatformMetrics
from paysentineliq.interface.api.dependencies import get_readiness_checker
from paysentineliq.interface.api.problems import build_problem_response

router = APIRouter(tags=["ops"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready")
async def ready(
    checker: Annotated[ReadinessChecker, Depends(get_readiness_checker)],
) -> JSONResponse:
    status = await checker.check()
    is_ready = status.database and status.cache
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={
            "status": "ready" if is_ready else "not_ready",
            "checks": {
                "postgres": status.database,
                "redis": status.cache,
            },
        },
    )


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    settings = request.app.state.settings
    provided = request.headers.get("X-Metrics-Token")
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    expected = settings.metrics_token
    if not expected or provided is None or not secrets.compare_digest(provided, expected):
        return build_problem_response(
            request,
            status_code=401,
            code="metrics_unauthorized",
            title="Unauthorized",
            detail="Metrics credential required.",
            extra_headers={"WWW-Authenticate": "Bearer"},
        )
    platform_metrics: PlatformMetrics | None = getattr(request.app.state, "metrics", None)
    if platform_metrics is None:
        return build_problem_response(
            request,
            status_code=503,
            code="metrics_unavailable",
            title="Service unavailable",
            detail="Metrics are unavailable.",
        )
    return Response(
        content=platform_metrics.render(),
        media_type=platform_metrics.content_type,
    )
