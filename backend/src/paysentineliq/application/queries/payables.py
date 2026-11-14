from dataclasses import dataclass
from datetime import date
from uuid import UUID

from paysentineliq.application.ports.payables import PayableReadRepositoryPort
from paysentineliq.application.queries.payable_cursor import (
    decode_payable_cursor,
    encode_payable_cursor,
)
from paysentineliq.domain.payables import Payable, PayableStatus


@dataclass(frozen=True, slots=True)
class PayableListDTO:
    items: tuple[Payable, ...]
    next_cursor: str | None


class ListPayablesHandler:
    def __init__(self, repository: PayableReadRepositoryPort) -> None:
        self._repository = repository

    async def handle(
        self,
        owner_id: UUID,
        *,
        statuses: tuple[PayableStatus, ...] = (),
        due_from: date | None = None,
        due_to: date | None = None,
        limit: int,
        cursor: str | None = None,
    ) -> PayableListDTO:
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        before = decode_payable_cursor(cursor) if cursor else None
        items = await self._repository.list_for_owner(
            owner_id,
            statuses=statuses,
            due_from=due_from,
            due_to=due_to,
            limit=limit + 1,
            before=before,
        )
        has_more = len(items) > limit
        page = items[:limit]
        next_cursor = (
            encode_payable_cursor(page[-1].due_date, page[-1].id) if has_more and page else None
        )
        return PayableListDTO(items=page, next_cursor=next_cursor)
