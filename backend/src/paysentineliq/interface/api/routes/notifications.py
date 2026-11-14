from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from paysentineliq.application.commands.notifications import (
    NotificationCommandHandler,
    NotificationPreferenceHandler,
    NotificationPreferencesDTO,
    PreferenceUpdate,
)
from paysentineliq.application.locale import SUPPORTED_LOCALES
from paysentineliq.application.queries.notifications import ListNotificationsHandler
from paysentineliq.domain.notification import (
    DeliveryChannel,
    Notification,
    NotificationType,
    is_e164,
)
from paysentineliq.domain.user import User
from paysentineliq.interface.api.dependencies import (
    get_current_user,
    get_notification_command_handler,
    get_notification_list_query,
    get_notification_preference_handler,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])
preferences_router = APIRouter(
    prefix="/notification-preferences",
    tags=["notifications"],
)


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    payload: dict[str, str]
    read: bool
    read_at: datetime | None
    created_at: datetime | None


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    next_cursor: str | None


class UnreadCountResponse(BaseModel):
    unread: int


class ReadAllResponse(BaseModel):
    updated: int


class ChannelPreferenceRequest(BaseModel):
    enabled: bool = False
    destination: str | None = None
    consent: bool = False


class NotificationPreferencesRequest(BaseModel):
    locale: str | None = None
    email: ChannelPreferenceRequest = Field(default_factory=ChannelPreferenceRequest)
    sms: ChannelPreferenceRequest = Field(default_factory=ChannelPreferenceRequest)
    whatsapp: ChannelPreferenceRequest = Field(default_factory=ChannelPreferenceRequest)

    @field_validator("locale")
    @classmethod
    def _validate_locale(cls, value: str | None) -> str | None:
        if value is not None and value not in SUPPORTED_LOCALES:
            raise ValueError("locale is not supported")
        return value

    @model_validator(mode="after")
    def _validate_channels(self) -> Self:
        for name, channel in (("sms", self.sms), ("whatsapp", self.whatsapp)):
            if channel.destination is not None and not is_e164(channel.destination):
                raise ValueError(f"{name} destination must use E.164")
            if channel.enabled and not channel.consent:
                raise ValueError(f"{name} requires explicit consent")
            if channel.enabled and channel.destination is None:
                raise ValueError(f"{name} destination is required when enabled")
        return self


class ChannelPreferenceResponse(BaseModel):
    channel: str
    enabled: bool
    destination: str | None
    consented_at: datetime | None


class NotificationPreferencesResponse(BaseModel):
    locale: str
    timezone: str
    channels: list[ChannelPreferenceResponse]


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[ListNotificationsHandler, Depends(get_notification_list_query)],
) -> UnreadCountResponse:
    return UnreadCountResponse(unread=await handler.unread_count(user.id))


@router.post("/read-all", response_model=ReadAllResponse)
async def mark_all_read(
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[
        NotificationCommandHandler,
        Depends(get_notification_command_handler),
    ],
) -> ReadAllResponse:
    return ReadAllResponse(updated=await handler.mark_all_read(user.id))


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[ListNotificationsHandler, Depends(get_notification_list_query)],
    type: Annotated[list[NotificationType] | None, Query()] = None,
    unread: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> NotificationListResponse:
    result = await handler.handle(
        user.id,
        types=tuple(type or ()),
        unread_only=bool(unread),
        limit=limit,
        cursor=cursor,
    )
    return NotificationListResponse(
        items=[_notification_response(item) for item in result.items],
        next_cursor=result.next_cursor,
    )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[
        NotificationCommandHandler,
        Depends(get_notification_command_handler),
    ],
) -> NotificationResponse:
    return _notification_response(await handler.mark_read(notification_id, user.id))


@router.delete("/{notification_id}", status_code=204)
async def delete_notification(
    notification_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[
        NotificationCommandHandler,
        Depends(get_notification_command_handler),
    ],
) -> None:
    await handler.delete(notification_id, user.id)


@preferences_router.get("", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[
        NotificationPreferenceHandler,
        Depends(get_notification_preference_handler),
    ],
) -> NotificationPreferencesResponse:
    return _preferences_response(await handler.get(user))


@preferences_router.put("", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    payload: NotificationPreferencesRequest,
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[
        NotificationPreferenceHandler,
        Depends(get_notification_preference_handler),
    ],
) -> NotificationPreferencesResponse:
    updates = (
        PreferenceUpdate(
            channel=DeliveryChannel.EMAIL,
            enabled=payload.email.enabled,
            consent=payload.email.consent,
        ),
        PreferenceUpdate(
            channel=DeliveryChannel.SMS,
            enabled=payload.sms.enabled,
            destination=payload.sms.destination,
            consent=payload.sms.consent,
        ),
        PreferenceUpdate(
            channel=DeliveryChannel.WHATSAPP,
            enabled=payload.whatsapp.enabled,
            destination=payload.whatsapp.destination,
            consent=payload.whatsapp.consent,
        ),
    )
    result = await handler.update(
        user,
        locale=payload.locale or user.preferred_locale,
        updates=updates,
    )
    return _preferences_response(result)


def _notification_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        type=notification.type.value,
        payload=dict(notification.payload),
        read=notification.is_read,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


def _preferences_response(
    result: NotificationPreferencesDTO,
) -> NotificationPreferencesResponse:
    return NotificationPreferencesResponse(
        locale=result.locale,
        timezone=result.timezone,
        channels=[
            ChannelPreferenceResponse(
                channel=preference.channel.value,
                enabled=preference.enabled,
                destination=preference.destination_masked,
                consented_at=preference.consented_at,
            )
            for preference in result.channels
        ],
    )
