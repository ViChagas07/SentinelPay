from uuid import UUID, uuid4

import pytest

from paysentineliq.application.queries.example import (
    ExampleStatusDTO,
    GetExampleHandler,
    GetExampleQuery,
)
from paysentineliq.domain.errors import NotFoundError

pytestmark = pytest.mark.unit


class FakeRepository:
    def __init__(self, found: bool) -> None:
        self._found = found
        self.calls = 0

    async def exists(self, item_id: UUID) -> bool:
        self.calls += 1
        return self._found


def _handler(found: bool) -> tuple[GetExampleHandler, FakeRepository]:
    repository = FakeRepository(found)
    handler: GetExampleHandler = GetExampleHandler(repository)
    return handler, repository


async def test_query_returns_dto_without_unit_of_work() -> None:
    handler, repository = _handler(found=True)
    item_id = uuid4()

    result = await handler.handle(GetExampleQuery(item_id=item_id))

    assert result == ExampleStatusDTO(item_id=item_id, status="ok")
    assert repository.calls == 1


async def test_query_raises_document_not_found() -> None:
    handler, _ = _handler(found=False)

    with pytest.raises(NotFoundError) as error:
        await handler.handle(GetExampleQuery(item_id=UUID(int=0)))

    assert error.value.code == "document_not_found"
    assert error.value.status_code == 404
