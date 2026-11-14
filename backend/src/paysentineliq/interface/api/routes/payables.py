from datetime import date, datetime, time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from paysentineliq.application.commands.payables import (
    PayableCommandHandler,
    ReminderPreferenceHandler,
)
from paysentineliq.application.queries.payables import ListPayablesHandler
from paysentineliq.domain.payables import (
    NotificationChannel,
    Payable,
    PayableStatus,
)
from paysentineliq.domain.user import User
from paysentineliq.interface.api.dependencies import (
    get_current_user,
    get_payable_command_handler,
    get_payable_list_query,
    get_reminder_preference_handler,
)

router = APIRouter(prefix="/payables", tags=["payables"])


class PayableResponse(BaseModel):
    id: UUID
    analysis_id: UUID
    description: str
    amount: str
    due_date: date
    status: str
    created_at: datetime | None
    updated_at: datetime | None


class PayableListResponse(BaseModel):
    items: list[PayableResponse]
    next_cursor: str | None


class RescheduleRequest(BaseModel):
    due_date: date


class ReminderPreferenceRequest(BaseModel):
    offsets_days: list[int] = Field(default_factory=lambda: [3, 1, 0])
    local_time: time = time(9, 0)
    channels: list[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.IN_APP],
    )


class ReminderPreferenceResponse(BaseModel):
    offsets_days: list[int]
    local_time: time
    channels: list[str]
    timezone: str


@router.get("/reminder-preferences", response_model=ReminderPreferenceResponse)
async def get_reminder_preferences(
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[
        ReminderPreferenceHandler,
        Depends(get_reminder_preference_handler),
    ],
) -> ReminderPreferenceResponse:
    preference = await handler.get(user.id)
    return ReminderPreferenceResponse(
        offsets_days=list(preference.offsets_days),
        local_time=preference.local_time,
        channels=[channel.value for channel in preference.channels],
        timezone=user.timezone,
    )


@router.put("/reminder-preferences", response_model=ReminderPreferenceResponse)
async def update_reminder_preferences(
    payload: ReminderPreferenceRequest,
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[
        ReminderPreferenceHandler,
        Depends(get_reminder_preference_handler),
    ],
) -> ReminderPreferenceResponse:
    preference = await handler.update(
        user.id,
        offsets_days=tuple(payload.offsets_days),
        local_time=payload.local_time,
        channels=tuple(payload.channels),
    )
    return ReminderPreferenceResponse(
        offsets_days=list(preference.offsets_days),
        local_time=preference.local_time,
        channels=[channel.value for channel in preference.channels],
        timezone=user.timezone,
    )


@router.get("", response_model=PayableListResponse)
async def list_payables(
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[ListPayablesHandler, Depends(get_payable_list_query)],
    status: Annotated[list[PayableStatus] | None, Query()] = None,
    due_from: Annotated[date | None, Query()] = None,
    due_to: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> PayableListResponse:
    result = await handler.handle(
        user.id,
        statuses=tuple(status or ()),
        due_from=due_from,
        due_to=due_to,
        limit=limit,
        cursor=cursor,
    )
    return PayableListResponse(
        items=[_response(item) for item in result.items],
        next_cursor=result.next_cursor,
    )


@router.post("/{payable_id}/confirm", response_model=PayableResponse)
async def confirm_payable(
    payable_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[PayableCommandHandler, Depends(get_payable_command_handler)],
) -> PayableResponse:
    return _response(await handler.confirm(payable_id, user.id))


@router.post("/{payable_id}/pay", response_model=PayableResponse)
async def pay_payable(
    payable_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[PayableCommandHandler, Depends(get_payable_command_handler)],
) -> PayableResponse:
    return _response(await handler.pay(payable_id, user.id))


@router.post("/{payable_id}/dismiss", response_model=PayableResponse)
async def dismiss_payable(
    payable_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[PayableCommandHandler, Depends(get_payable_command_handler)],
) -> PayableResponse:
    return _response(await handler.dismiss(payable_id, user.id))


@router.patch("/{payable_id}/due-date", response_model=PayableResponse)
async def reschedule_payable(
    payable_id: UUID,
    payload: RescheduleRequest,
    user: Annotated[User, Depends(get_current_user)],
    handler: Annotated[PayableCommandHandler, Depends(get_payable_command_handler)],
) -> PayableResponse:
    return _response(await handler.reschedule(payable_id, user.id, payload.due_date))


def _response(payable: Payable) -> PayableResponse:
    return PayableResponse(
        id=payable.id,
        analysis_id=payable.analysis_id,
        description=payable.description,
        amount=f"{payable.amount_cents // 100}.{payable.amount_cents % 100:02d}",
        due_date=payable.due_date,
        status=payable.status.value,
        created_at=payable.created_at,
        updated_at=payable.updated_at,
    )
