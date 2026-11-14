import asyncio
import os
import time
from datetime import date, timedelta
from uuid import UUID

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from paysentineliq.infrastructure.db.models import (
    AnalysisEventModel,
    AnalysisModel,
    DocumentModel,
    NotificationDeliveryModel,
    NotificationModel,
    NotificationPreferenceModel,
    PayableModel,
    ReminderPreferenceModel,
    UserModel,
)
from paysentineliq.interface.api.routes.analyses import AnalysisKind
from tests.integration.test_analysis_queue_e2e import (
    _API_URL,
    _auth,
    _create_user,
    _pdf,
    _wait_for_terminal,
)
from tests.support.receipt_factory import build_receipt

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_MAILPIT_URL = os.environ.get("MAILPIT_URL", "http://127.0.0.1:8025")


async def test_event_creates_central_item_email_and_respects_consent() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owners: list[UUID] = []
    analyses: list[UUID] = []
    try:
        owner = await _create_user(factory, "notifications")
        other = await _create_user(factory, "notifications-other")
        owners = [owner.id, other.id]
        header = _auth(owner)
        other_header = _auth(other)
        today = date.today()
        receipt = build_receipt(
            due_date=today + timedelta(days=10),
            reference=f"{today:%m/%Y}",
        )

        async with httpx.AsyncClient(base_url=_API_URL, timeout=30) as client:
            first = await _upload(client, header, receipt.ocr_text(), AnalysisKind.RECEIPT)
            analyses.append(first)
            first_detail = await _wait_for_terminal(client, first, header)
            assert first_detail["status"] in {"completed", "degraded"}

        first_notification = await _wait_for_notification(factory, first)
        assert first_notification.type == "receipt_analyzed"
        email_delivery = await _wait_for_delivery(
            factory,
            first_notification.id,
            "email",
            expected_status="sent",
        )
        assert email_delivery.status == "sent"
        for channel in ("sms", "whatsapp"):
            delivery = await _wait_for_delivery(
                factory,
                first_notification.id,
                channel,
                expected_status="skipped",
            )
            assert delivery.last_error_safe == "channel_disabled"

        message = await _wait_for_mailpit_email(owner.email)
        subject = str(message["Subject"])
        body = str(message["Text"])
        assert "Recibo" in subject
        assert "184.75" not in body
        assert "Energia Sul" not in body

        async with httpx.AsyncClient(base_url=_API_URL, timeout=30) as client:
            central = await client.get("/api/v1/notifications", headers=header)
            assert central.status_code == 200, central.text
            items = central.json()["items"]
            assert any(item["id"] == str(first_notification.id) for item in items)

            count = await client.get("/api/v1/notifications/unread-count", headers=header)
            assert count.status_code == 200
            assert count.json()["unread"] >= 1

            foreign = await client.get("/api/v1/notifications", headers=other_header)
            assert foreign.status_code == 200
            assert all(item["id"] != str(first_notification.id) for item in foreign.json()["items"])
            forbidden = await client.delete(
                f"/api/v1/notifications/{first_notification.id}",
                headers=other_header,
            )
            assert forbidden.status_code == 404
            assert forbidden.json()["code"] == "notification_not_found"

            read = await client.post(
                f"/api/v1/notifications/{first_notification.id}/read",
                headers=header,
            )
            assert read.status_code == 200
            assert read.json()["read"] is True

            preferences = await client.put(
                "/api/v1/notification-preferences",
                headers=header,
                json={
                    "locale": "pt-BR",
                    "email": {"enabled": True},
                    "sms": {
                        "enabled": True,
                        "destination": "+5511999999999",
                        "consent": True,
                    },
                    "whatsapp": {
                        "enabled": True,
                        "destination": "+5511888888888",
                        "consent": True,
                    },
                },
            )
            assert preferences.status_code == 200, preferences.text
            channels = {item["channel"]: item for item in preferences.json()["channels"]}
            assert channels["sms"]["enabled"] is True
            assert channels["sms"]["destination"] == "+55*******9999"
            assert channels["sms"]["consented_at"] is not None

            second = await _upload(client, header, receipt.ocr_text(), AnalysisKind.RECEIPT)
            analyses.append(second)
            second_detail = await _wait_for_terminal(client, second, header)
            assert second_detail["status"] in {"completed", "degraded"}

        second_notification = await _wait_for_notification(factory, second)
        for channel in ("email", "sms", "whatsapp"):
            delivery = await _wait_for_delivery(
                factory,
                second_notification.id,
                channel,
                expected_status="sent",
            )
            assert delivery.status == "sent"
            assert delivery.attempts == 0
    finally:
        async with factory() as session:
            if owners:
                await session.execute(
                    delete(NotificationDeliveryModel).where(
                        NotificationDeliveryModel.notification_id.in_(
                            select(NotificationModel.id).where(
                                NotificationModel.owner_id.in_(owners),
                            ),
                        ),
                    ),
                )
                await session.execute(
                    delete(NotificationModel).where(NotificationModel.owner_id.in_(owners)),
                )
                await session.execute(
                    delete(NotificationPreferenceModel).where(
                        NotificationPreferenceModel.user_id.in_(owners),
                    ),
                )
                await session.execute(
                    delete(ReminderPreferenceModel).where(
                        ReminderPreferenceModel.user_id.in_(owners),
                    ),
                )
                await session.execute(
                    delete(PayableModel).where(PayableModel.owner_id.in_(owners)),
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
                await session.execute(
                    delete(DocumentModel).where(DocumentModel.owner_id.in_(owners)),
                )
            if owners:
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


async def _wait_for_notification(
    factory: async_sessionmaker[AsyncSession],
    analysis_id: UUID,
    *,
    timeout_seconds: float = 60,
) -> NotificationModel:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        async with factory() as session:
            notification = await session.scalar(
                select(NotificationModel).where(
                    NotificationModel.analysis_id == analysis_id,
                ),
            )
        if notification is not None:
            return notification
        await asyncio.sleep(0.5)
    raise AssertionError("notification was not created")


async def _wait_for_delivery(
    factory: async_sessionmaker[AsyncSession],
    notification_id: UUID,
    channel: str,
    *,
    expected_status: str,
    timeout_seconds: float = 60,
) -> NotificationDeliveryModel:
    deadline = time.monotonic() + timeout_seconds
    last: NotificationDeliveryModel | None = None
    while time.monotonic() < deadline:
        async with factory() as session:
            delivery = await session.scalar(
                select(NotificationDeliveryModel).where(
                    NotificationDeliveryModel.notification_id == notification_id,
                    NotificationDeliveryModel.channel == channel,
                ),
            )
        if delivery is not None:
            last = delivery
            if delivery.status == expected_status:
                return delivery
        await asyncio.sleep(0.5)
    raise AssertionError(f"delivery {channel} did not reach {expected_status}: {last}")


async def _wait_for_mailpit_email(
    to_email: str,
    *,
    timeout_seconds: float = 60,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    async with httpx.AsyncClient(base_url=_MAILPIT_URL, timeout=10) as client:
        while time.monotonic() < deadline:
            response = await client.get(
                "/api/v1/search",
                params={"query": f"to:{to_email}"},
            )
            if response.status_code == 200:
                messages = response.json().get("messages", [])
                if messages:
                    message_id = messages[0]["ID"]
                    detail = await client.get(f"/api/v1/message/{message_id}")
                    if detail.status_code == 200:
                        return dict(detail.json())
            await asyncio.sleep(0.5)
    raise AssertionError(f"no Mailpit email for {to_email}")
