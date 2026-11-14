from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from paysentineliq.application.ports.readiness import ReadinessChecker
from paysentineliq.interface.api.dependencies import get_readiness_checker

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
