import pytest

from paysentineliq.application.locale import SUPPORTED_LOCALES
from paysentineliq.application.notifications.templates import render_notification
from paysentineliq.domain.notification import NotificationType

pytestmark = pytest.mark.unit

_ALL_TYPES = tuple(NotificationType)


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
@pytest.mark.parametrize("notification_type", _ALL_TYPES)
def test_every_supported_locale_renders_every_type(
    locale: str,
    notification_type: NotificationType,
) -> None:
    template = render_notification(
        locale=locale,
        notification_type=notification_type,
        days=3,
    )

    assert template.subject.strip()
    assert template.body.strip()


def test_unknown_locale_falls_back_to_english() -> None:
    unknown = render_notification(
        locale="xx-YY",
        notification_type=NotificationType.PAYABLE_DUE_SOON,
        days=3,
    )
    english = render_notification(
        locale="en",
        notification_type=NotificationType.PAYABLE_DUE_SOON,
        days=3,
    )

    assert unknown == english


def test_locale_variants_are_normalized() -> None:
    assert render_notification(
        locale="pt",
        notification_type=NotificationType.PAYABLE_DUE_TODAY,
    ) == render_notification(
        locale="pt-BR",
        notification_type=NotificationType.PAYABLE_DUE_TODAY,
    )
    assert render_notification(
        locale="en-US",
        notification_type=NotificationType.PAYABLE_DUE_TODAY,
    ) == render_notification(
        locale="en",
        notification_type=NotificationType.PAYABLE_DUE_TODAY,
    )


def test_due_soon_includes_days_without_sensitive_data() -> None:
    template = render_notification(
        locale="pt-BR",
        notification_type=NotificationType.PAYABLE_DUE_SOON,
        days=3,
    )

    assert "3" in template.body
    for forbidden in ("R$", "CPF", "CNPJ", "score", "código de barras", "codigo de barras"):
        assert forbidden not in template.body


def test_legacy_reminder_type_maps_to_due_soon_or_today() -> None:
    soon = render_notification(
        locale="en",
        notification_type=NotificationType.PAYABLE_DUE_REMINDER,
        days=3,
    )
    today = render_notification(
        locale="en",
        notification_type=NotificationType.PAYABLE_DUE_REMINDER,
        days=0,
    )

    assert soon == render_notification(
        locale="en",
        notification_type=NotificationType.PAYABLE_DUE_SOON,
        days=3,
    )
    assert today == render_notification(
        locale="en",
        notification_type=NotificationType.PAYABLE_DUE_TODAY,
    )
