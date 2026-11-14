from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_ZERO_UUID = "00000000-0000-0000-0000-000000000000"


class SqlAlchemyExampleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists(self, item_id: UUID) -> bool:
        statement = text("SELECT CAST(:item_id AS uuid) <> CAST(:zero AS uuid)")
        result = await self._session.execute(
            statement,
            {"item_id": str(item_id), "zero": _ZERO_UUID},
        )
        return bool(result.scalar_one())
