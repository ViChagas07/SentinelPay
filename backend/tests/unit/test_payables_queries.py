from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest

from paysentineliq.application.errors import InvalidCursorError
from paysentineliq.application.queries.payable_cursor import (
    decode_payable_cursor,
    encode_payable_cursor,
)
from paysentineliq.application.queries.payables import ListPayablesHandler
from paysentineliq.domain.payables import Payable, PayableStatus

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_OWNER = uuid4()


def _payable(index: int) -> Payable:
    return Payable(
        id=uuid4(),
        owner_id=_OWNER,
        analysis_id=uuid4(),
        description=f"Conta {index}",
        amount_cents=1000 + index,
        due_date=date(2026, 1, 10 + index),
        status=PayableStatus.PENDING,
        created_at=_NOW,
        updated_at=_NOW,
    )


class FakeReadRepository:
    def __init__(self, items: tuple[Payable, ...]) -> None:
        self._items = items
        self.calls: list[dict[str, object]] = []

    async def get_for_owner(self, payable_id: UUID, owner_id: UUID) -> Payable | None:
        return None

    async def list_for_owner(
        self,
        owner_id: UUID,
        *,
        statuses: tuple[PayableStatus, ...] = (),
        due_from: date | None = None,
        due_to: date | None = None,
        limit: int,
        before: tuple[date, UUID] | None = None,
    ) -> tuple[Payable, ...]:
        self.calls.append(
            {
                "owner_id": owner_id,
                "statuses": statuses,
                "due_from": due_from,
                "due_to": due_to,
                "limit": limit,
                "before": before,
            },
        )
        filtered = [
            item
            for item in self._items
            if (not statuses or item.status in statuses)
            and (due_from is None or item.due_date >= due_from)
            and (due_to is None or item.due_date <= due_to)
            and (before is None or (item.due_date, item.id) > before)
        ]
        filtered.sort(key=lambda item: (item.due_date, item.id))
        return tuple(filtered[:limit])


async def test_list_uses_cursor_and_passes_filters() -> None:
    repository = FakeReadRepository(tuple(_payable(index) for index in range(3)))
    handler = ListPayablesHandler(repository)

    first = await handler.handle(
        _OWNER,
        statuses=(PayableStatus.PENDING,),
        due_from=date(2026, 1, 1),
        limit=2,
    )
    assert len(first.items) == 2
    assert first.next_cursor is not None
    second = await handler.handle(_OWNER, limit=2, cursor=first.next_cursor)

    assert len(second.items) == 1
    assert second.next_cursor is None
    assert repository.calls[0]["statuses"] == (PayableStatus.PENDING,)
    assert repository.calls[0]["limit"] == 3


def test_payable_cursor_roundtrip_and_invalid() -> None:
    payable_id = uuid4()
    cursor = encode_payable_cursor(date(2026, 1, 15), payable_id)

    assert decode_payable_cursor(cursor) == (date(2026, 1, 15), payable_id)
    with pytest.raises(InvalidCursorError):
        decode_payable_cursor("not-a-cursor")


async def test_limit_is_bounded() -> None:
    handler = ListPayablesHandler(FakeReadRepository(()))

    with pytest.raises(ValueError):
        await handler.handle(_OWNER, limit=0)
