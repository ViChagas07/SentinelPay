from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class NotificationType(StrEnum):
    ANALYSIS_COMPLETED = "analysis_completed"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Notification:
    id: UUID
    owner_id: UUID
    analysis_id: UUID
    type: NotificationType
    payload: Mapping[str, str] = field(default_factory=dict)
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise ValueError("notification id must be a UUID")
        if not isinstance(self.owner_id, UUID):
            raise ValueError("owner_id must be a UUID")
        if not isinstance(self.analysis_id, UUID):
            raise ValueError("analysis_id must be a UUID")
        if len(self.payload) > 10:
            raise ValueError("notification payload is too large")
        for key, value in self.payload.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("notification payload must contain string keys and values")
            if len(key) > 64 or len(value) > 512:
                raise ValueError("notification payload item is too large")
