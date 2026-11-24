from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from paysentineliq.application.notifications.delivery import (
    NotificationDeliveryHandler,
)
from paysentineliq.application.ports.notifications import DeliveryContext
from paysentineliq.domain.notification import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationStatus,
    NotificationType,
)
from paysentineliq.infrastructure.observability.metrics import PlatformMetrics

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class _FakeSender:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict[str, str]] = []
        self.error = error


class FakeEmailAdapter(_FakeSender):
    async def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> None:
        self.calls.append({"to": to, "subject": subject, "body": body})
        if self.error is not None:
            raise self.error


class FakeSmsAdapter(_FakeSender):
    async def send(self, *, to: str, body: str) -> None:
        self.calls.append({"to": to, "body": body})
        if self.error is not None:
            raise self.error


class FakeWhatsAppAdapter(_FakeSender):
    async def send(self, *, to: str, body: str) -> None:
        self.calls.append({"to": to, "body": body})
        if self.error is not None:
            raise self.error


class FakeDeliveryRepository:
    def __init__(self, context: DeliveryContext | None) -> None:
        self.context = context
        self.deliveries: dict[tuple[UUID, DeliveryChannel], NotificationDelivery] = {}
        self.notification_status: NotificationStatus = (
            context.notification.status if context is not None else NotificationStatus.PENDING
        )
        self.status_updates: list[NotificationStatus] = []

    async def get_context(self, notification_id: UUID) -> DeliveryContext | None:
        if self.context is None or self.context.notification.id != notification_id:
            return None
        return self.context

    async def get_or_create(
        self,
        notification_id: UUID,
        channel: DeliveryChannel,
        now: datetime,
    ) -> NotificationDelivery:
        key = (notification_id, channel)
        if key not in self.deliveries:
            self.deliveries[key] = NotificationDelivery(
                id=uuid4(),
                notification_id=notification_id,
                channel=channel,
                created_at=now,
                updated_at=now,
            )
        return self.deliveries[key]

    async def mark_sent(self, delivery_id: UUID, now: datetime) -> None:
        self._replace(
            delivery_id,
            status=DeliveryStatus.SENT,
            sent_at=now,
            last_error_safe=None,
            updated_at=now,
        )

    async def mark_failed(self, delivery_id: UUID, error_safe: str, now: datetime) -> None:
        delivery = self._find(delivery_id)
        self._replace(
            delivery_id,
            status=DeliveryStatus.FAILED,
            attempts=delivery.attempts + 1,
            last_error_safe=error_safe,
            updated_at=now,
        )

    async def mark_skipped(self, delivery_id: UUID, reason_safe: str, now: datetime) -> None:
        self._replace(
            delivery_id,
            status=DeliveryStatus.SKIPPED,
            last_error_safe=reason_safe,
            updated_at=now,
        )

    async def set_notification_status(
        self,
        notification_id: UUID,
        status: NotificationStatus,
        now: datetime,
    ) -> None:
        self.notification_status = status
        self.status_updates.append(status)

    def _find(self, delivery_id: UUID) -> NotificationDelivery:
        for delivery in self.deliveries.values():
            if delivery.id == delivery_id:
                return delivery
        raise AssertionError("delivery not found")

    def _replace(self, delivery_id: UUID, **changes: object) -> None:
        for key, delivery in list(self.deliveries.items()):
            if delivery.id == delivery_id:
                self.deliveries[key] = replace(delivery, **changes)  # type: ignore[arg-type]


def _context(
    *,
    locale: str = "pt-BR",
    status: NotificationStatus = NotificationStatus.PENDING,
    sms_enabled: bool = False,
    whatsapp_enabled: bool = False,
) -> DeliveryContext:
    user_id = uuid4()
    notification = Notification(
        id=uuid4(),
        owner_id=user_id,
        analysis_id=uuid4(),
        type=NotificationType.PAYABLE_DUE_SOON,
        payload={
            "payable_id": str(uuid4()),
            "due_date": "2026-01-15",
            "offset_days": "3",
            "type": "payable_due_soon",
            "channel": "in_app",
        },
        status=status,
        created_at=_NOW,
    )
    consented_at = datetime(2025, 12, 1, tzinfo=UTC)
    preferences = (
        NotificationPreference(
            channel=DeliveryChannel.EMAIL,
            enabled=True,
            destination="user@example.com",
            consented_at=consented_at,
        ),
        NotificationPreference(
            channel=DeliveryChannel.SMS,
            enabled=sms_enabled,
            destination="+5511999999999" if sms_enabled else None,
            consented_at=consented_at if sms_enabled else None,
        ),
        NotificationPreference(
            channel=DeliveryChannel.WHATSAPP,
            enabled=whatsapp_enabled,
            destination="+5511888888888" if whatsapp_enabled else None,
            consented_at=consented_at if whatsapp_enabled else None,
        ),
    )
    return DeliveryContext(
        notification=notification,
        email="user@example.com",
        locale=locale,
        timezone="America/Sao_Paulo",
        preferences=preferences,
    )


def _handler(
    context: DeliveryContext,
    *,
    email_error: Exception | None = None,
    sms_error: Exception | None = None,
    whatsapp_error: Exception | None = None,
    metrics: PlatformMetrics | None = None,
) -> tuple[
    NotificationDeliveryHandler,
    FakeDeliveryRepository,
    FakeEmailAdapter,
    FakeSmsAdapter,
    FakeWhatsAppAdapter,
]:
    repository = FakeDeliveryRepository(context)
    email = FakeEmailAdapter(email_error)
    sms = FakeSmsAdapter(sms_error)
    whatsapp = FakeWhatsAppAdapter(whatsapp_error)
    handler = NotificationDeliveryHandler(
        repository,
        email,
        sms,
        whatsapp,
        clock=lambda: _NOW,
        metrics=metrics,
    )
    return handler, repository, email, sms, whatsapp


async def test_missing_opt_in_skips_sms_and_whatsapp_but_sends_email() -> None:
    context = _context()
    handler, repository, email, sms, whatsapp = _handler(context)

    outcome = await handler.execute(context.notification.id)

    assert outcome.status == "delivered"
    assert outcome.sent == (DeliveryChannel.EMAIL,)
    assert set(outcome.skipped) == {DeliveryChannel.SMS, DeliveryChannel.WHATSAPP}
    assert len(email.calls) == 1
    assert sms.calls == []
    assert whatsapp.calls == []
    assert repository.notification_status.value == "dispatched"


async def test_unknown_locale_falls_back_to_english() -> None:
    from paysentineliq.application.notifications.templates import render_notification

    context = _context(locale="xx-YY")
    handler, _, email, _, _ = _handler(context)

    await handler.execute(context.notification.id)

    english = render_notification(
        locale="en",
        notification_type=NotificationType.PAYABLE_DUE_SOON,
        days=3,
    )
    assert email.calls[0]["subject"] == english.subject
    assert email.calls[0]["body"] == english.body


async def test_one_channel_failure_does_not_block_others_and_retry_only_failed() -> None:
    context = _context(sms_enabled=True, whatsapp_enabled=True)
    handler, repository, email, sms, whatsapp = _handler(
        context,
        sms_error=RuntimeError("provider down at +5511999999999"),
    )

    first = await handler.execute(context.notification.id)

    assert first.status == "retry"
    assert first.failed == (DeliveryChannel.SMS,)
    assert set(first.sent) == {DeliveryChannel.EMAIL, DeliveryChannel.WHATSAPP}
    assert len(email.calls) == 1
    assert len(whatsapp.calls) == 1
    assert len(sms.calls) == 1
    assert repository.notification_status.value == "pending"
    failed_delivery = repository.deliveries[(context.notification.id, DeliveryChannel.SMS)]
    assert failed_delivery.status is DeliveryStatus.FAILED
    assert failed_delivery.attempts == 1
    assert "+5511999999999" not in (failed_delivery.last_error_safe or "")

    sms.error = None
    second = await handler.execute(context.notification.id)

    assert second.status == "delivered"
    assert second.failed == ()
    assert len(email.calls) == 1
    assert len(whatsapp.calls) == 1
    assert len(sms.calls) == 2
    assert repository.notification_status.value == "dispatched"


async def test_second_run_is_idempotent_and_does_not_resend() -> None:
    context = _context(sms_enabled=True, whatsapp_enabled=True)
    handler, _, email, sms, whatsapp = _handler(context)

    await handler.execute(context.notification.id)
    await handler.execute(context.notification.id)

    assert len(email.calls) == 1
    assert len(sms.calls) == 1
    assert len(whatsapp.calls) == 1


async def test_final_attempt_marks_notification_failed_but_keeps_it() -> None:
    context = _context(sms_enabled=True)
    handler, repository, _, _sms, _ = _handler(
        context,
        sms_error=RuntimeError("permanent"),
    )

    outcome = await handler.execute(context.notification.id, final_attempt=True)

    assert outcome.status == "failed"
    assert outcome.failed == (DeliveryChannel.SMS,)
    assert repository.notification_status.value == "failed"
    assert repository.context is not None
    assert repository.context.notification.id == context.notification.id


async def test_cancelled_notification_is_not_sent() -> None:
    context = _context(status=NotificationStatus.CANCELLED, sms_enabled=True)
    handler, repository, email, sms, whatsapp = _handler(context)

    outcome = await handler.execute(context.notification.id)

    assert outcome.status == "cancelled"
    assert email.calls == []
    assert sms.calls == []
    assert whatsapp.calls == []
    assert all(
        delivery.status is DeliveryStatus.SKIPPED for delivery in repository.deliveries.values()
    )


async def test_delivery_records_channel_status_metrics() -> None:
    context = _context(sms_enabled=True)
    metrics = PlatformMetrics(multiprocess=False)
    handler, _, _, _, _ = _handler(context, metrics=metrics)

    await handler.execute(context.notification.id)

    text = metrics.render().decode("utf-8")
    assert 'channel="email"' in text
    assert 'channel="sms"' in text
    assert 'channel="whatsapp"' in text
    assert 'status="sent"' in text
    assert 'status="skipped"' in text


async def test_missing_notification_returns_not_found() -> None:
    handler, _, _, _, _ = _handler(_context())

    outcome = await handler.execute(uuid4())

    assert outcome.status == "not_found"
