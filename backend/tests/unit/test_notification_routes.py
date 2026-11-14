from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from paysentineliq.application.commands.notifications import PreferenceUpdate
from paysentineliq.application.errors import NotificationNotFoundError
from paysentineliq.application.queries.notifications import NotificationListDTO
from paysentineliq.domain.notification import (
    DeliveryChannel,
    Notification,
    NotificationPreference,
    NotificationStatus,
    NotificationType,
)
from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.interface.api.dependencies import (
    get_current_user,
    get_notification_command_handler,
    get_notification_list_query,
    get_notification_preference_handler,
)
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_USER = User(
    id=uuid4(),
    google_sub="google-sub",
    email="user@example.com",
    name="User",
    preferred_locale="pt-BR",
    timezone="America/Sao_Paulo",
    role=Role.USER,
)


def _notification(
    *,
    notification_type: NotificationType = NotificationType.ANALYSIS_COMPLETED,
    read_at: datetime | None = None,
) -> Notification:
    return Notification(
        id=uuid4(),
        owner_id=_USER.id,
        analysis_id=uuid4(),
        type=notification_type,
        payload={"analysis_id": str(uuid4()), "status": "completed"},
        status=NotificationStatus.PENDING,
        created_at=_NOW,
        read_at=read_at,
    )


class FakeListHandler:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def handle(self, owner_id: UUID, **kwargs: Any) -> NotificationListDTO:
        self.calls.append({"owner_id": owner_id, **kwargs})
        return NotificationListDTO(items=(_notification(),), next_cursor="next")

    async def unread_count(self, owner_id: UUID) -> int:
        self.calls.append({"owner_id": owner_id, "unread_count": True})
        return 0


class FakeCommandHandler:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, UUID, UUID]] = []

    async def mark_read(self, notification_id: UUID, owner_id: UUID) -> Notification:
        self.calls.append(("read", notification_id, owner_id))
        if self.error is not None:
            raise self.error
        return _notification(read_at=_NOW)

    async def mark_all_read(self, owner_id: UUID) -> int:
        self.calls.append(("read_all", uuid4(), owner_id))
        if self.error is not None:
            raise self.error
        return 3

    async def delete(self, notification_id: UUID, owner_id: UUID) -> None:
        self.calls.append(("delete", notification_id, owner_id))
        if self.error is not None:
            raise self.error


class FakePreferenceHandler:
    def __init__(self) -> None:
        self.updated: tuple[str, tuple[PreferenceUpdate, ...]] | None = None

    async def get(self, user: User) -> Any:
        from paysentineliq.application.commands.notifications import (
            NotificationPreferencesDTO,
        )

        return NotificationPreferencesDTO(
            locale=user.preferred_locale,
            timezone=user.timezone,
            channels=(
                NotificationPreference(
                    channel=DeliveryChannel.EMAIL,
                    enabled=True,
                    destination=user.email,
                    consented_at=_NOW,
                ),
                NotificationPreference(channel=DeliveryChannel.SMS),
                NotificationPreference(channel=DeliveryChannel.WHATSAPP),
            ),
        )

    async def update(
        self,
        user: User,
        *,
        locale: str,
        updates: tuple[PreferenceUpdate, ...],
    ) -> Any:
        self.updated = (locale, updates)
        return await self.get(user)


def _app(
    *,
    listing: FakeListHandler | None = None,
    command: FakeCommandHandler | None = None,
    preferences: FakePreferenceHandler | None = None,
    authenticated: bool = True,
) -> Any:
    app = create_app(Settings(app_env="local"))
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: _USER
    if listing is not None:
        app.dependency_overrides[get_notification_list_query] = lambda: listing
    if command is not None:
        app.dependency_overrides[get_notification_command_handler] = lambda: command
    if preferences is not None:
        app.dependency_overrides[get_notification_preference_handler] = lambda: preferences
    return app


async def _request(
    app: Any,
    method: str,
    path: str,
    **kwargs: Any,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


async def test_list_notifications_filters_and_cursor() -> None:
    listing = FakeListHandler()

    response = await _request(
        _app(listing=listing),
        "GET",
        "/api/v1/notifications?type=payable_due_soon&type=high_risk_detected&unread=true&limit=10",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["type"] == "analysis_completed"
    assert payload["items"][0]["read"] is False
    assert payload["next_cursor"] == "next"
    call = listing.calls[0]
    assert call["owner_id"] == _USER.id
    assert call["types"] == (
        NotificationType.PAYABLE_DUE_SOON,
        NotificationType.HIGH_RISK_DETECTED,
    )
    assert call["unread_only"] is True
    assert call["limit"] == 10


async def test_unread_count() -> None:
    response = await _request(
        _app(listing=FakeListHandler()),
        "GET",
        "/api/v1/notifications/unread-count",
    )

    assert response.status_code == 200
    assert response.json() == {"unread": 0}


async def test_mark_read_and_read_all_use_owner() -> None:
    command = FakeCommandHandler()
    notification_id = uuid4()
    app = _app(command=command)

    read = await _request(app, "POST", f"/api/v1/notifications/{notification_id}/read")
    read_all = await _request(app, "POST", "/api/v1/notifications/read-all")

    assert read.status_code == 200
    assert read.json()["read"] is True
    assert read_all.status_code == 200
    assert read_all.json() == {"updated": 3}
    assert command.calls[0] == ("read", notification_id, _USER.id)
    assert command.calls[1][0] == "read_all"
    assert command.calls[1][2] == _USER.id


async def test_delete_and_idor_maps_to_404() -> None:
    command = FakeCommandHandler(error=NotificationNotFoundError())
    notification_id = uuid4()

    response = await _request(
        _app(command=command),
        "DELETE",
        f"/api/v1/notifications/{notification_id}",
    )

    assert response.status_code == 404
    assert response.json()["code"] == "notification_not_found"
    assert command.calls[0] == ("delete", notification_id, _USER.id)


async def test_preferences_get_masks_destinations() -> None:
    response = await _request(
        _app(preferences=FakePreferenceHandler()),
        "GET",
        "/api/v1/notification-preferences",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["locale"] == "pt-BR"
    assert payload["timezone"] == "America/Sao_Paulo"
    email = next(item for item in payload["channels"] if item["channel"] == "email")
    assert email["enabled"] is True
    assert email["destination"] == "u***@example.com"


async def test_preferences_update_records_opt_in() -> None:
    preferences = FakePreferenceHandler()

    response = await _request(
        _app(preferences=preferences),
        "PUT",
        "/api/v1/notification-preferences",
        json={
            "locale": "ja",
            "sms": {"enabled": True, "destination": "+5511999999999", "consent": True},
            "whatsapp": {"enabled": False, "consent": False},
        },
    )

    assert response.status_code == 200
    assert preferences.updated is not None
    locale, updates = preferences.updated
    assert locale == "ja"
    sms = next(item for item in updates if item.channel is DeliveryChannel.SMS)
    assert sms.enabled is True
    assert sms.destination == "+5511999999999"
    assert sms.consent is True


async def test_preferences_reject_sms_without_consent_or_invalid_phone() -> None:
    app = _app(preferences=FakePreferenceHandler())

    no_consent = await _request(
        app,
        "PUT",
        "/api/v1/notification-preferences",
        json={"sms": {"enabled": True, "destination": "+5511999999999", "consent": False}},
    )
    invalid_phone = await _request(
        app,
        "PUT",
        "/api/v1/notification-preferences",
        json={"sms": {"enabled": True, "destination": "11999999999", "consent": True}},
    )

    assert no_consent.status_code == 422
    assert invalid_phone.status_code == 422


async def test_preferences_reject_unknown_locale() -> None:
    response = await _request(
        _app(preferences=FakePreferenceHandler()),
        "PUT",
        "/api/v1/notification-preferences",
        json={"locale": "xx-YY"},
    )

    assert response.status_code == 422


async def test_notifications_endpoints_require_auth() -> None:
    response = await _request(
        _app(listing=FakeListHandler(), authenticated=False),
        "GET",
        "/api/v1/notifications",
    )

    assert response.status_code in {401, 403}
