from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from paysentineliq.infrastructure.config import Settings, get_settings
from paysentineliq.infrastructure.logging import configure_logging
from paysentineliq.interface.api.middleware import RequestIdMiddleware
from paysentineliq.interface.api.problems import register_exception_handlers


class HealthResponse(BaseModel):
    status: Literal["ok"]


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)

    app = FastAPI(title="PaySentinelIQ", version="0.1.0")
    app.state.settings = resolved_settings
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    return app


app = create_app()
