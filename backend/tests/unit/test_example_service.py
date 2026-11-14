from types import TracebackType
from uuid import UUID, uuid4

import pytest

from paysentineliq.application.ports.repository import ExampleRepository
from paysentineliq.application.use_cases.example import ExampleService
from paysentineliq.domain.errors import NotFoundError

pytestmark = pytest.mark.unit


class FakeRepository:
    def __init__(self, found: bool) -> None:
        self._found = found

    async def exists(self, item_id: UUID) -> bool:
        return self._found


class FakeUnitOfWork:
    def __init__(self, repository: ExampleRepository) -> None:
        self.examples = repository
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def _service(found: bool) -> tuple[ExampleService, FakeUnitOfWork]:
    uow = FakeUnitOfWork(FakeRepository(found))
    return ExampleService(uow), uow


async def test_check_commits_when_found() -> None:
    service, uow = _service(found=True)

    assert await service.check(uuid4()) is True
    assert uow.committed is True


async def test_check_raises_document_not_found() -> None:
    service, _ = _service(found=False)

    with pytest.raises(NotFoundError) as error:
        await service.check(UUID(int=0))

    assert error.value.code == "document_not_found"
    assert error.value.status_code == 404
