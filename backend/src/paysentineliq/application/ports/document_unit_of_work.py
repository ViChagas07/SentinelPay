from types import TracebackType
from typing import Protocol, Self

from paysentineliq.application.ports.document_write_repository import (
    DocumentWriteRepository,
)


class DocumentUnitOfWork(Protocol):
    @property
    def documents(self) -> DocumentWriteRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
