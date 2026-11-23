from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuthEvent:
    event_type: str
    user_id: UUID | None = None
    created_ip: str | None = None
    created_user_agent: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    occurred_at: datetime | None = None
