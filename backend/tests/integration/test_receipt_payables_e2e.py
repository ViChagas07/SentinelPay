import asyncio
import os
import time
from datetime import date, timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from paysentineliq.domain.payables import PayableStatus
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.db.models import (
    AnalysisEventModel,
    AnalysisModel,
    DocumentModel,
    NotificationModel,
    PayableModel,
    ReminderPreferenceModel,
    UserModel,
)
from paysentineliq.infrastructure.messaging.celery_app import (
    PAYABLES_REMINDER_TASK,
    build_celery_app,
)
from paysentineliq.interface.api.routes.analyses import AnalysisKind
from tests.integration.test_analysis_queue_e2e import (
    _API_URL,
    _RABBITMQ_URL,
    _auth,
    _create_user,
    _pdf,
    _wait_for_terminal,
)
from tests.support.receipt_factory import build_receipt

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_receipt_creates_payable_and_reminder_but_tampered_does_not() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owners: list[UUID] = []
    analyses: list[UUID] = []
    try:
        owner = await _create_user(factory, "payables")
        other = await _create_user(factory, "payables-other")
        owners = [owner.id, other.id]
        today = date.today()
        receipt = build_receipt(
            due_date=today + timedelta(days=2),
            reference=f"{today:%m/%Y}",
        )
        header = _auth(owner)

        async with httpx.AsyncClient(base_url=_API_URL, timeout=30) as client:
            valid = await _upload(client, header, receipt.ocr_text(), AnalysisKind.RECEIPT)
            valid_detail = await _wait_for_terminal(client, valid, header)
            assert valid_detail["status"] in {"completed", "degraded"}
            assert valid_detail["result"]["band"] in {"low", "attention"}
            analyses.append(valid)

            payables = await client.get("/api/v1/payables", headers=header)
            assert payables.status_code == 200, payables.text
            items = payables.json()["items"]
            assert len(items) == 1
            payable = items[0]
            assert payable["analysis_id"] == str(valid)
            assert payable["amount"] == "184.75"
            assert payable["status"] in {
                PayableStatus.PENDING.value,
                PayableStatus.PENDING_CONFIRMATION.value,
            }

            foreign_confirm = await client.post(
                f"/api/v1/payables/{payable['id']}/confirm",
                headers=_auth(other),
            )
            assert foreign_confirm.status_code == 404

            reminder_app = build_celery_app(
                Settings(
                    app_env="local",
                    rabbitmq_url=_RABBITMQ_URL,
                    celery_result_backend="cache+memory://",
                ),
            )
            reminder_app.send_task(PAYABLES_REMINDER_TASK, queue="scheduler")
            reminder_app.send_task(PAYABLES_REMINDER_TASK, queue="scheduler")
            first_count = await _wait_for_reminder(factory, UUID(payable["id"]))

            tampered = build_receipt(
                due_date=today + timedelta(days=2),
                reference=f"{today:%m/%Y}",
            ).with_tampered_dv()
            bad = await _upload(client, header, tampered.ocr_text(), AnalysisKind.RECEIPT)
            bad_detail = await _wait_for_terminal(client, bad, header)
            analyses.append(bad)
            assert bad_detail["status"] in {"completed", "degraded"}
            assert bad_detail["result"]["band"] == "high"

        async with factory() as session:
            bad_payables = await session.scalar(
                select(func.count(PayableModel.id)).where(PayableModel.analysis_id == bad),
            )
            duplicate_count = await session.scalar(
                select(func.count(NotificationModel.id)).where(
                    NotificationModel.payable_id == UUID(payable["id"]),
                    NotificationModel.type == "payable_due_soon",
                    NotificationModel.reminder_offset_days == 3,
                    NotificationModel.channel == "in_app",
                ),
            )
        assert first_count >= 1
        assert duplicate_count == 1
        assert bad_payables == 0
    finally:
        async with factory() as session:
            if owners:
                await session.execute(
                    delete(NotificationModel).where(NotificationModel.owner_id.in_(owners)),
                )
                await session.execute(
                    delete(PayableModel).where(PayableModel.owner_id.in_(owners)),
                )
                await session.execute(
                    delete(ReminderPreferenceModel).where(
                        ReminderPreferenceModel.user_id.in_(owners),
                    ),
                )
            if analyses:
                await session.execute(
                    delete(AnalysisEventModel).where(
                        AnalysisEventModel.analysis_id.in_(analyses),
                    ),
                )
                await session.execute(
                    delete(AnalysisModel).where(AnalysisModel.id.in_(analyses)),
                )
            if owners:
                await session.execute(
                    delete(DocumentModel).where(DocumentModel.owner_id.in_(owners)),
                )
                await session.execute(delete(UserModel).where(UserModel.id.in_(owners)))
            await session.commit()
        await engine.dispose()


async def _upload(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    text: str,
    kind: AnalysisKind,
) -> UUID:
    response = await client.post(
        "/api/v1/analyses",
        data={"kind": kind.value},
        files={"file": ("receipt.pdf", _pdf(text), "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    return UUID(response.json()["analysis_id"])


async def _wait_for_reminder(
    factory: async_sessionmaker[AsyncSession],
    payable_id: UUID,
    *,
    timeout_seconds: float = 30,
) -> int:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        async with factory() as session:
            count = await session.scalar(
                select(func.count(NotificationModel.id)).where(
                    NotificationModel.payable_id == payable_id,
                    NotificationModel.type == "payable_due_soon",
                ),
            )
        if count:
            return int(count)
        await asyncio.sleep(0.5)
    return 0
