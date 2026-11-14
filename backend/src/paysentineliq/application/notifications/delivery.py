import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from paysentineliq.application.notifications.templates import render_notification
from paysentineliq.application.ports.messaging import EmailPort, SmsPort, WhatsAppPort
from paysentineliq.application.ports.notifications import (
    DeliveryContext,
    NotificationDeliveryRepositoryPort,
)
from paysentineliq.domain.notification import (
    DeliveryChannel,
    DeliveryStatus,
    NotificationPreference,
    NotificationStatus,
    NotificationType,
)

_logger = logging.getLogger("paysentineliq")

_CHANNELS = (DeliveryChannel.EMAIL, DeliveryChannel.SMS, DeliveryChannel.WHATSAPP)
_SAFE_ERRORS = {
    DeliveryChannel.EMAIL: "smtp_error",
    DeliveryChannel.SMS: "sms_provider_error",
    DeliveryChannel.WHATSAPP: "whatsapp_provider_error",
}
_SAFE_REASONS = {
    "disabled": "channel_disabled",
    "consent": "consent_missing",
    "destination": "destination_missing",
    "cancelled": "notification_cancelled",
}


@dataclass(frozen=True, slots=True)
class DeliveryOutcome:
    notification_id: UUID
    status: Literal["delivered", "retry", "failed", "cancelled", "not_found"]
    sent: tuple[DeliveryChannel, ...] = field(default_factory=tuple)
    skipped: tuple[DeliveryChannel, ...] = field(default_factory=tuple)
    failed: tuple[DeliveryChannel, ...] = field(default_factory=tuple)


class NotificationDeliveryHandler:
    def __init__(
        self,
        repository: NotificationDeliveryRepositoryPort,
        email: EmailPort,
        sms: SmsPort,
        whatsapp: WhatsAppPort,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._email = email
        self._sms = sms
        self._whatsapp = whatsapp
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self,
        notification_id: UUID,
        *,
        final_attempt: bool = False,
    ) -> DeliveryOutcome:
        context = await self._repository.get_context(notification_id)
        if context is None:
            return DeliveryOutcome(notification_id=notification_id, status="not_found")
        now = self._clock()
        sent: list[DeliveryChannel] = []
        skipped: list[DeliveryChannel] = []
        failed: list[DeliveryChannel] = []
        for channel in _CHANNELS:
            delivery = await self._repository.get_or_create(notification_id, channel, now)
            if delivery.status is DeliveryStatus.SENT:
                sent.append(channel)
                continue
            if delivery.status is DeliveryStatus.SKIPPED:
                skipped.append(channel)
                continue
            if context.notification.status is NotificationStatus.CANCELLED:
                await self._repository.mark_skipped(
                    delivery.id,
                    _SAFE_REASONS["cancelled"],
                    now,
                )
                skipped.append(channel)
                continue
            preference = context.preference_for(channel)
            reason = _skip_reason(channel, preference, context)
            if reason is not None:
                await self._repository.mark_skipped(delivery.id, reason, now)
                skipped.append(channel)
                continue
            template = render_notification(
                locale=context.locale,
                notification_type=context.notification.type,
                days=_reminder_days(context),
            )
            try:
                await self._send(channel, context, preference, template.subject, template.body)
            except Exception:
                safe_error = _SAFE_ERRORS[channel]
                await self._repository.mark_failed(delivery.id, safe_error, now)
                _logger.warning(
                    "notification_delivery_failed channel=%s error=%s",
                    channel.value,
                    safe_error,
                )
                failed.append(channel)
            else:
                await self._repository.mark_sent(delivery.id, now)
                sent.append(channel)
        if context.notification.status is NotificationStatus.CANCELLED:
            return DeliveryOutcome(
                notification_id=notification_id,
                status="cancelled",
                sent=tuple(sent),
                skipped=tuple(skipped),
                failed=tuple(failed),
            )
        if failed:
            status: Literal["failed", "retry"] = "failed" if final_attempt else "retry"
            if final_attempt:
                await self._repository.set_notification_status(
                    notification_id,
                    NotificationStatus.FAILED,
                    now,
                )
            return DeliveryOutcome(
                notification_id=notification_id,
                status=status,
                sent=tuple(sent),
                skipped=tuple(skipped),
                failed=tuple(failed),
            )
        await self._repository.set_notification_status(
            notification_id,
            NotificationStatus.DISPATCHED,
            now,
        )
        return DeliveryOutcome(
            notification_id=notification_id,
            status="delivered",
            sent=tuple(sent),
            skipped=tuple(skipped),
        )

    async def _send(
        self,
        channel: DeliveryChannel,
        context: DeliveryContext,
        preference: NotificationPreference,
        subject: str,
        body: str,
    ) -> None:
        if channel is DeliveryChannel.EMAIL:
            await self._email.send(
                to=preference.destination or context.email,
                subject=subject,
                body=body,
            )
            return
        destination = preference.destination
        if destination is None:
            raise ValueError("phone destination is missing")
        if channel is DeliveryChannel.SMS:
            await self._sms.send(to=destination, body=body)
        else:
            await self._whatsapp.send(to=destination, body=body)


def _skip_reason(
    channel: DeliveryChannel,
    preference: NotificationPreference,
    context: DeliveryContext,
) -> str | None:
    if not preference.enabled:
        return _SAFE_REASONS["disabled"]
    if channel is DeliveryChannel.EMAIL:
        if not (preference.destination or context.email):
            return _SAFE_REASONS["destination"]
        return None
    if preference.consented_at is None:
        return _SAFE_REASONS["consent"]
    if preference.destination is None:
        return _SAFE_REASONS["destination"]
    return None


def _reminder_days(context: DeliveryContext) -> int | None:
    notification = context.notification
    if notification.type is NotificationType.PAYABLE_DUE_TODAY:
        return 0
    if notification.type is not NotificationType.PAYABLE_DUE_SOON:
        return None
    raw = notification.payload.get("offset_days", "1")
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1
