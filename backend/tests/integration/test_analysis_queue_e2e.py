import asyncio
import os
import time
from typing import Any
from uuid import UUID, uuid4

import httpx
import pymupdf
import pytest
from kombu import Connection
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.db.models import (
    AnalysisEventModel,
    AnalysisModel,
    DocumentModel,
    NotificationModel,
    UserModel,
)
from paysentineliq.infrastructure.messaging.celery_app import (
    ANALYSIS_TASK,
    build_celery_app,
)
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService
from tests.support.boleto_factory import build_boleto

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
_RABBITMQ_URL = os.environ.get(
    "RABBITMQ_URL",
    "amqp://sentinel:CHANGE_ME@127.0.0.1:5672//",
)
_JWT_SECRET = os.environ.get("JWT_SECRET", "CHANGE_ME_USE_AT_LEAST_32_RANDOM_BYTES")


def _pdf(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    y = 40
    for line in text.splitlines():
        page.insert_text((30, y), line, fontsize=9)
        y += 16
    data = document.tobytes()
    document.close()
    return bytes(data)


def _auth(user: User) -> dict[str, str]:
    token = JwtAccessTokenService(secret=_JWT_SECRET, ttl_minutes=15).issue(user)
    return {"Authorization": f"Bearer {token.token}"}


async def _create_user(
    factory: async_sessionmaker[AsyncSession],
    suffix: str,
) -> User:
    async with factory() as session, session.begin():
        model = UserModel(
            google_sub=f"e2e-{suffix}-{uuid4().hex}",
            email=f"e2e-{suffix}-{uuid4().hex}@example.com",
            name="E2E User",
        )
        session.add(model)
        await session.flush()
        return User(
            id=model.id,
            google_sub=model.google_sub,
            email=model.email,
            name=model.name,
            preferred_locale=model.preferred_locale,
            timezone=model.timezone,
            role=Role(model.role),
        )


async def test_upload_worker_completes_and_duplicate_delivery_is_idempotent() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owner: User | None = None
    other: User | None = None
    analysis_id: UUID | None = None
    document_id: UUID | None = None
    try:
        owner = await _create_user(factory, "owner")
        other = await _create_user(factory, "other")
        pdf = _pdf(build_boleto().ocr_text())
        idempotency_key = f"e2e-{uuid4().hex}"

        async with httpx.AsyncClient(base_url=_API_URL, timeout=30) as client:
            headers = {**_auth(owner), "Idempotency-Key": idempotency_key}
            first = await client.post(
                "/api/v1/analyses",
                data={"kind": "boleto"},
                files={"file": ("boleto.pdf", pdf, "application/pdf")},
                headers=headers,
            )
            assert first.status_code == 202, first.text
            analysis_id = UUID(first.json()["analysis_id"])

            replay = await client.post(
                "/api/v1/analyses",
                data={"kind": "boleto"},
                files={"file": ("boleto.pdf", pdf, "application/pdf")},
                headers=headers,
            )
            assert replay.status_code == 202, replay.text
            assert replay.json()["analysis_id"] == str(analysis_id)
            assert replay.headers.get("Idempotency-Replayed") == "true"

            detail = await _wait_for_terminal(client, analysis_id, _auth(owner))
            assert detail["status"] in {"completed", "degraded"}
            result = detail["result"]
            assert result is not None
            assert 0 <= result["score"] <= 100
            assert result["band"] in {"low", "medium", "high", "critical"}
            assert result["justification"]
            assert isinstance(result["evidence"], list)
            assert "fields" not in result

            forbidden = await client.get(
                f"/api/v1/analyses/{analysis_id}",
                headers=_auth(other),
            )
            assert forbidden.status_code == 404
            assert forbidden.json()["code"] == "analysis_not_found"

        async with factory() as session:
            model = await session.get(AnalysisModel, analysis_id)
            assert model is not None
            document_id = model.document_id
            notifications = (
                await session.scalars(
                    select(NotificationModel).where(
                        NotificationModel.analysis_id == analysis_id,
                    ),
                )
            ).all()
            events = (
                await session.scalars(
                    select(AnalysisEventModel).where(
                        AnalysisEventModel.analysis_id == analysis_id,
                    ),
                )
            ).all()
        assert len(notifications) == 1
        assert notifications[0].status == "pending"
        assert set(notifications[0].payload) == {
            "analysis_id",
            "document_type",
            "status",
            "score",
            "band",
        }
        event_types = {event.event_type for event in events}
        assert {"queued", "processing", "completed"} <= event_types

        duplicate_app = build_celery_app(
            Settings(
                app_env="local",
                rabbitmq_url=_RABBITMQ_URL,
                celery_result_backend="cache+memory://",
            ),
        )
        duplicate_app.send_task(
            ANALYSIS_TASK,
            args=[str(analysis_id), "pt"],
            queue="analysis",
        )
        await asyncio.sleep(3)

        async with factory() as session:
            completed_events = await session.scalar(
                select(func.count(AnalysisEventModel.id)).where(
                    AnalysisEventModel.analysis_id == analysis_id,
                    AnalysisEventModel.event_type == "completed",
                ),
            )
            notification_count = await session.scalar(
                select(func.count(NotificationModel.id)).where(
                    NotificationModel.analysis_id == analysis_id,
                ),
            )
            status = await session.scalar(
                select(AnalysisModel.status).where(AnalysisModel.id == analysis_id),
            )
        assert completed_events == 1
        assert notification_count == 1
        assert status in {"completed", "degraded"}

        with Connection(_RABBITMQ_URL) as connection:
            channel = connection.channel()
            channel.queue_declare(queue="analysis", passive=True)
            channel.queue_declare(queue="analysis.dlq", passive=True)
    finally:
        async with factory() as session:
            if analysis_id is not None:
                await session.execute(
                    delete(NotificationModel).where(
                        NotificationModel.analysis_id == analysis_id,
                    ),
                )
                await session.execute(
                    delete(AnalysisEventModel).where(
                        AnalysisEventModel.analysis_id == analysis_id,
                    ),
                )
                await session.execute(
                    delete(AnalysisModel).where(AnalysisModel.id == analysis_id),
                )
            if document_id is not None:
                await session.execute(
                    delete(DocumentModel).where(DocumentModel.id == document_id),
                )
            if owner is not None:
                await session.execute(delete(UserModel).where(UserModel.id == owner.id))
            if other is not None:
                await session.execute(delete(UserModel).where(UserModel.id == other.id))
            await session.commit()
        await engine.dispose()


async def _wait_for_terminal(
    client: httpx.AsyncClient,
    analysis_id: UUID,
    headers: dict[str, str],
    *,
    timeout_seconds: float = 90,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        async with httpx.AsyncClient(base_url=_API_URL, timeout=30) as poller:
            response = await poller.get(
                f"/api/v1/analyses/{analysis_id}",
                headers=headers,
            )
        if response.status_code == 429:
            await asyncio.sleep(2)
            continue
        assert response.status_code == 200, response.text
        last = response.json()
        if last.get("status") in {"completed", "degraded", "failed"}:
            return last
        await asyncio.sleep(1)
    raise AssertionError(f"analysis did not finish in time: {last}")
