from types import TracebackType
from typing import Protocol, Self

from paysentineliq.application.ports.repository import ExampleRepository


class UnitOfWork(Protocol):
    @property
    def examples(self) -> ExampleRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
