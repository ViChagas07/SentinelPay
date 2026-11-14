from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from paysentineliq.application.ports.document_repository import DocumentRepository
from paysentineliq.domain.analysis import AnalysisEvent, AnalysisRecord


class AnalysisCreationRepositoryPort(Protocol):
    async def lock_idempotency(self, owner_id: UUID, idempotency_key: str) -> None: ...

    async def find_by_idempotency(
        self,
        owner_id: UUID,
        idempotency_key: str,
    ) -> AnalysisRecord | None: ...

    async def lock_quota(self, owner_id: UUID) -> None: ...

    async def count_active_for_owner(self, owner_id: UUID) -> int: ...

    async def add(
        self,
        record: AnalysisRecord,
        *,
        event: AnalysisEvent | None = None,
    ) -> None: ...


class AnalysisUnitOfWork(Protocol):
    @property
    def documents(self) -> DocumentRepository: ...

    @property
    def analyses(self) -> AnalysisCreationRepositoryPort: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
