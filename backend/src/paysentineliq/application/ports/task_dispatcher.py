from typing import Protocol
from uuid import UUID


class TaskDispatcherPort(Protocol):
    def dispatch_analysis(self, analysis_id: UUID, *, locale: str = "pt") -> None: ...

    def dispatch_notification(self, notification_id: UUID) -> None: ...

    def revoke_analysis(self, task_id: str) -> None: ...
