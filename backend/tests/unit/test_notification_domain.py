from uuid import uuid4

import pytest

from paysentineliq.domain.notification import (
    Notification,
    NotificationStatus,
    NotificationType,
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
