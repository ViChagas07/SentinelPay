from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from paysentineliq.domain.user import User
from paysentineliq.interface.api.dependencies import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


class UserProfile(BaseModel):
    id: UUID
    email: str
    name: str | None
    role: str
    preferred_locale: str
    timezone: str


@router.get("/me", response_model=UserProfile)
async def me(
    user: Annotated[User, Depends(get_current_user)],
) -> UserProfile:
    return UserProfile(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role.value,
        preferred_locale=user.preferred_locale,
        timezone=user.timezone,
    )
