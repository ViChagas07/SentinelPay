from types import TracebackType
from typing import Protocol, Self

from paysentineliq.application.ports.document_repository import DocumentRepository


class DocumentUnitOfWork(Protocol):
    @property
    def documents(self) -> DocumentRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
