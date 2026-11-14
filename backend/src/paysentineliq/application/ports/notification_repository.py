from typing import Protocol
from uuid import UUID

from paysentineliq.domain.notification import Notification


class NotificationRepositoryPort(Protocol):
    async def list_pending_for_analysis(
        self,
        analysis_id: UUID,
    ) -> tuple[Notification, ...]: ...

    async def mark_dispatched(self, notification_id: UUID) -> None: ...
