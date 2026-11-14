from dataclasses import dataclass, field
from uuid import UUID

from paysentineliq.application.ports.notifications import (
    NotificationCenterRepositoryPort,
)
from paysentineliq.application.queries.analysis_cursor import decode_cursor, encode_cursor
from paysentineliq.domain.notification import Notification, NotificationType


@dataclass(frozen=True, slots=True)
class NotificationListDTO:
    items: tuple[Notification, ...] = field(default_factory=tuple)
    next_cursor: str | None = None


class ListNotificationsHandler:
    def __init__(self, repository: NotificationCenterRepositoryPort) -> None:
        self._repository = repository

    async def handle(
        self,
        owner_id: UUID,
        *,
        types: tuple[NotificationType, ...] = (),
        unread_only: bool = False,
        limit: int,
        cursor: str | None = None,
    ) -> NotificationListDTO:
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        before = decode_cursor(cursor) if cursor else None
        items = await self._repository.list_for_owner(
            owner_id,
            types=types,
            unread_only=unread_only,
            limit=limit + 1,
            before=before,
        )
        has_more = len(items) > limit
        page = items[:limit]
        next_cursor = (
            encode_cursor(page[-1].created_at, page[-1].id)
            if has_more and page and page[-1].created_at is not None
            else None
        )
        return NotificationListDTO(items=page, next_cursor=next_cursor)

    async def unread_count(self, owner_id: UUID) -> int:
        return await self._repository.unread_count(owner_id)
