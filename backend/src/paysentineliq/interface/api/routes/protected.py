from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from paysentineliq.domain.user import Role, User
from paysentineliq.interface.api.dependencies import (
    get_current_user,
    require_role,
)

router = APIRouter(prefix="/protected", tags=["protected"])


class ProtectedResponse(BaseModel):
    user_id: UUID
    role: str


@router.get("/user", response_model=ProtectedResponse)
async def protected_user(
    user: Annotated[User, Depends(get_current_user)],
) -> ProtectedResponse:
    return ProtectedResponse(user_id=user.id, role=user.role.value)


@router.get("/admin", response_model=ProtectedResponse)
async def protected_admin(
    user: Annotated[User, Depends(require_role(Role.ADMIN))],
) -> ProtectedResponse:
    return ProtectedResponse(user_id=user.id, role=user.role.value)
