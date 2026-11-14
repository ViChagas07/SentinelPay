from datetime import UTC, datetime
from uuid import uuid4

import pytest

from paysentineliq.domain.notification import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationStatus,
    NotificationType,
    mask_destination,
)

pytestmark = pytest.mark.unit


def test_notification_requires_string_payload_within_limits() -> None:
    notification = Notification(
        id=uuid4(),
        owner_id=uuid4(),
        analysis_id=uuid4(),
        type=NotificationType.ANALYSIS_COMPLETED,
        payload={"analysis_id": str(uuid4()), "status": "completed"},
    )

    assert notification.status is NotificationStatus.PENDING
    assert notification.created_at is None
    assert notification.read_at is None


def test_notification_rejects_non_string_payload() -> None:
    with pytest.raises(ValueError):
        Notification(
            id=uuid4(),
            owner_id=uuid4(),
            analysis_id=uuid4(),
            type=NotificationType.ANALYSIS_COMPLETED,
            payload={"score": 10},  # type: ignore[dict-item]
        )


def test_notification_rejects_oversized_payload() -> None:
    with pytest.raises(ValueError):
        Notification(
            id=uuid4(),
            owner_id=uuid4(),
            analysis_id=uuid4(),
            type=NotificationType.ANALYSIS_COMPLETED,
            payload={f"key-{index}": "value" for index in range(11)},
        )


def test_notification_types_cover_external_channels() -> None:
    assert {item.value for item in NotificationType} >= {
        "analysis_completed",
        "high_risk_detected",
        "receipt_analyzed",
        "payable_due_soon",
        "payable_due_today",
        "payable_overdue",
    }
    assert {item.value for item in DeliveryChannel} == {"email", "sms", "whatsapp"}


def test_sms_preference_requires_consent_and_e164() -> None:
    with pytest.raises(ValueError):
        NotificationPreference(channel=DeliveryChannel.SMS, enabled=True, destination="+5511")

    with pytest.raises(ValueError):
        NotificationPreference(
            channel=DeliveryChannel.SMS,
            enabled=True,
            destination="+5511999999999",
        )

    preference = NotificationPreference(
        channel=DeliveryChannel.SMS,
        enabled=True,
        destination="+5511999999999",
        consented_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert preference.destination == "+5511999999999"


def test_sms_preference_rejects_invalid_phone_even_when_disabled() -> None:
    with pytest.raises(ValueError):
        NotificationPreference(channel=DeliveryChannel.WHATSAPP, destination="11999999999")


def test_email_preference_validates_destination() -> None:
    with pytest.raises(ValueError):
        NotificationPreference(channel=DeliveryChannel.EMAIL, enabled=True, destination="invalid")

    preference = NotificationPreference(
        channel=DeliveryChannel.EMAIL,
        enabled=True,
        destination="user@example.com",
    )
    assert preference.destination_masked == "u***@example.com"


def test_destination_masking_hides_phone_and_email() -> None:
    masked_phone = mask_destination(DeliveryChannel.SMS, "+5511999999999")
    masked_email = mask_destination(DeliveryChannel.EMAIL, "someone@example.com")

    assert masked_phone == "+55*******9999"
    assert "1999999999" not in masked_phone
    assert masked_email == "s***@example.com"
    assert "someone" not in masked_email


def test_notification_delivery_defaults_to_pending() -> None:
    delivery = NotificationDelivery(
        id=uuid4(),
        notification_id=uuid4(),
        channel=DeliveryChannel.EMAIL,
    )

    assert delivery.status is DeliveryStatus.PENDING
    assert delivery.attempts == 0
    assert delivery.last_error_safe is None
