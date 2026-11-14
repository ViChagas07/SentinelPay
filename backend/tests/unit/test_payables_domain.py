from datetime import date, time
from uuid import uuid4

import pytest

from paysentineliq.domain.notification import (
    Notification,
    NotificationStatus,
    NotificationType,
)
from paysentineliq.domain.payables import (
    NotificationChannel,
    Payable,
    PayableStatus,
    ReminderPreference,
    payable_status_for,
)
from paysentineliq.domain.scoring import RiskBand

pytestmark = pytest.mark.unit


def test_payable_status_policy_follows_risk_band() -> None:
    assert payable_status_for(RiskBand.LOW) is PayableStatus.PENDING
    assert payable_status_for(RiskBand.ATTENTION) is PayableStatus.PENDING_CONFIRMATION
    assert payable_status_for(RiskBand.HIGH) is None
    assert (
        payable_status_for(RiskBand.LOW, injection_detected=True)
        is PayableStatus.PENDING_CONFIRMATION
    )
    assert payable_status_for(RiskBand.HIGH, injection_detected=True) is None


def test_payable_rejects_zero_amount_and_empty_description() -> None:
    def build(*, amount_cents: int = 100, description: str = "Conta de luz") -> Payable:
        return Payable(
            id=uuid4(),
            owner_id=uuid4(),
            analysis_id=uuid4(),
            description=description,
            amount_cents=amount_cents,
            due_date=date(2026, 1, 10),
            status=PayableStatus.PENDING,
        )

    with pytest.raises(ValueError):
        build(amount_cents=0)
    with pytest.raises(ValueError):
        build(description="   ")


def test_reminder_preference_defaults_and_validation() -> None:
    preference = ReminderPreference(user_id=uuid4())

    assert preference.offsets_days == (3, 1, 0)
    assert preference.local_time == time(9, 0)
    assert preference.channels == (NotificationChannel.IN_APP,)
    assert preference.sorted_offsets == (3, 1, 0)

    with pytest.raises(ValueError):
        ReminderPreference(user_id=uuid4(), offsets_days=(1, 1))
    with pytest.raises(ValueError):
        ReminderPreference(user_id=uuid4(), offsets_days=(31,))
    with pytest.raises(ValueError):
        ReminderPreference(user_id=uuid4(), channels=())


def test_reminder_notification_requires_due_date_and_offset_together() -> None:
    with pytest.raises(ValueError):
        Notification(
            id=uuid4(),
            owner_id=uuid4(),
            analysis_id=uuid4(),
            type=NotificationType.PAYABLE_DUE_REMINDER,
            reminder_due_date=date(2026, 1, 10),
        )

    notification = Notification(
        id=uuid4(),
        owner_id=uuid4(),
        analysis_id=uuid4(),
        type=NotificationType.PAYABLE_DUE_REMINDER,
        reminder_due_date=date(2026, 1, 10),
        reminder_offset_days=3,
        status=NotificationStatus.PENDING,
        channel=NotificationChannel.IN_APP,
    )
    assert notification.reminder_offset_days == 3
