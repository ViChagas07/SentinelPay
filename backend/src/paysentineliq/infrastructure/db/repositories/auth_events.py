from sqlalchemy.ext.asyncio import AsyncSession

from paysentineliq.domain.auth_event import AuthEvent
from paysentineliq.infrastructure.db.models import AuthEventModel


class SqlAlchemyAuthEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: AuthEvent) -> None:
        self._session.add(
            AuthEventModel(
                user_id=event.user_id,
                event_type=event.event_type,
                created_ip=event.created_ip,
                created_user_agent=event.created_user_agent,
                event_metadata=dict(event.metadata),
            )
        )
        await self._session.flush()
