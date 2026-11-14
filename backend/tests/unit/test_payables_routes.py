from datetime import UTC, date, datetime, time
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from paysentineliq.application.errors import PayableNotFoundError, PayableStateError
from paysentineliq.application.queries.payables import PayableListDTO
from paysentineliq.domain.payables import (
    NotificationChannel,
    Payable,
    PayableStatus,
    ReminderPreference,
)
from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.interface.api.dependencies import (
    get_current_user,
    get_payable_command_handler,
    get_payable_list_query,
    get_reminder_preference_handler,
)
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_USER = User(
    id=uuid4(),
    google_sub="google-sub",
    email="user@example.com",
    name="User",
    preferred_locale="pt-BR",
    timezone="America/Sao_Paulo",
    role=Role.USER,
)


def _payable(
    status: PayableStatus = PayableStatus.PENDING,
    *,
    payable_id: UUID | None = None,
) -> Payable:
    return Payable(
        id=payable_id or uuid4(),
        owner_id=_USER.id,
        analysis_id=uuid4(),
        description="Energia Sul - 01/2026",
        amount_cents=18475,
        due_date=date(2026, 1, 15),
        status=status,
        created_at=_NOW,
        updated_at=_NOW,
    )


class FakeCommandHandler:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, UUID, UUID, Any]] = []
        self._payable = _payable()

    async def confirm(self, payable_id: UUID, owner_id: UUID) -> Payable:
        self.calls.append(("confirm", payable_id, owner_id, None))
        if self.error is not None:
            raise self.error
        return self._payable

    async def pay(self, payable_id: UUID, owner_id: UUID) -> Payable:
        self.calls.append(("pay", payable_id, owner_id, None))
        if self.error is not None:
            raise self.error
        return self._payable

    async def dismiss(self, payable_id: UUID, owner_id: UUID) -> Payable:
        self.calls.append(("dismiss", payable_id, owner_id, None))
        if self.error is not None:
            raise self.error
        return self._payable

    async def reschedule(
        self,
        payable_id: UUID,
        owner_id: UUID,
        due_date: date,
    ) -> Payable:
        self.calls.append(("reschedule", payable_id, owner_id, due_date))
        if self.error is not None:
            raise self.error
        return self._payable


class FakeListHandler:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def handle(self, owner_id: UUID, **kwargs: Any) -> PayableListDTO:
        self.calls.append({"owner_id": owner_id, **kwargs})
        return PayableListDTO(items=(_payable(),), next_cursor="next")


class FakePreferenceHandler:
    def __init__(self) -> None:
        self.updated: ReminderPreference | None = None

    async def get(self, user_id: UUID) -> ReminderPreference:
        return ReminderPreference(user_id=user_id)

    async def update(
        self,
        user_id: UUID,
        *,
        offsets_days: tuple[int, ...],
        local_time: time,
        channels: tuple[NotificationChannel, ...],
    ) -> ReminderPreference:
        self.updated = ReminderPreference(
            user_id=user_id,
            offsets_days=offsets_days,
            local_time=local_time,
            channels=channels,
        )
        return self.updated


def _app(
    *,
    command: FakeCommandHandler | None = None,
    listing: FakeListHandler | None = None,
    preferences: FakePreferenceHandler | None = None,
    authenticated: bool = True,
) -> Any:
    app = create_app(Settings(app_env="local"))
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: _USER
    if command is not None:
        app.dependency_overrides[get_payable_command_handler] = lambda: command
    if listing is not None:
        app.dependency_overrides[get_payable_list_query] = lambda: listing
    if preferences is not None:
        app.dependency_overrides[get_reminder_preference_handler] = lambda: preferences
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


async def test_list_payables_filters_and_returns_cursor() -> None:
    listing = FakeListHandler()

    response = await _request(
        _app(listing=listing),
        "GET",
        "/api/v1/payables?status=pending&status=overdue&due_from=2026-01-01&limit=10",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["amount"] == "184.75"
    assert payload["next_cursor"] == "next"
    call = listing.calls[0]
    assert call["owner_id"] == _USER.id
    assert call["statuses"] == (PayableStatus.PENDING, PayableStatus.OVERDUE)
    assert call["due_from"] == date(2026, 1, 1)
    assert call["limit"] == 10


async def test_confirm_pay_and_dismiss_use_owner() -> None:
    command = FakeCommandHandler()
    payable_id = uuid4()
    app = _app(command=command)

    for action in ("confirm", "pay", "dismiss"):
        response = await _request(app, "POST", f"/api/v1/payables/{payable_id}/{action}")
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

    assert [item[0] for item in command.calls] == ["confirm", "pay", "dismiss"]
    assert all(item[2] == _USER.id for item in command.calls)


async def test_reschedule_passes_due_date() -> None:
    command = FakeCommandHandler()

    response = await _request(
        _app(command=command),
        "PATCH",
        f"/api/v1/payables/{uuid4()}/due-date",
        json={"due_date": "2026-02-01"},
    )

    assert response.status_code == 200
    assert command.calls[0][3] == date(2026, 2, 1)


async def test_idor_maps_to_404() -> None:
    command = FakeCommandHandler(error=PayableNotFoundError())

    response = await _request(
        _app(command=command),
        "POST",
        f"/api/v1/payables/{uuid4()}/confirm",
    )

    assert response.status_code == 404
    assert response.json()["code"] == "payable_not_found"


async def test_invalid_transition_maps_to_409() -> None:
    command = FakeCommandHandler(error=PayableStateError())

    response = await _request(
        _app(command=command),
        "POST",
        f"/api/v1/payables/{uuid4()}/pay",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "payable_invalid_state"


async def test_reminder_preferences_defaults_and_update() -> None:
    preferences = FakePreferenceHandler()
    app = _app(preferences=preferences)

    default = await _request(app, "GET", "/api/v1/payables/reminder-preferences")
    updated = await _request(
        app,
        "PUT",
        "/api/v1/payables/reminder-preferences",
        json={"offsets_days": [7, 0], "local_time": "18:30:00", "channels": ["in_app"]},
    )

    assert default.status_code == 200
    assert default.json()["offsets_days"] == [3, 1, 0]
    assert default.json()["timezone"] == "America/Sao_Paulo"
    assert updated.status_code == 200
    assert updated.json()["offsets_days"] == [7, 0]
    assert preferences.updated is not None
    assert preferences.updated.local_time == time(18, 30)


async def test_reminder_preferences_reject_unknown_channel() -> None:
    response = await _request(
        _app(preferences=FakePreferenceHandler()),
        "PUT",
        "/api/v1/payables/reminder-preferences",
        json={"offsets_days": [3], "channels": ["email"]},
    )

    assert response.status_code == 422


async def test_payables_endpoints_require_auth() -> None:
    response = await _request(
        _app(listing=FakeListHandler(), authenticated=False),
        "GET",
        "/api/v1/payables",
    )

    assert response.status_code in {401, 403}
