from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


def create_app() -> FastAPI:
    app = FastAPI(title="PaySentinelIQ", version="0.1.0")

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    return app


app = create_app()
