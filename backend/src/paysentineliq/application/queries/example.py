from dataclasses import dataclass
from uuid import UUID

from paysentineliq.application.ports.repository import ExampleRepository
from paysentineliq.domain.errors import NotFoundError


@dataclass(frozen=True, slots=True)
class GetExampleQuery:
    item_id: UUID


@dataclass(frozen=True, slots=True)
class ExampleStatusDTO:
    item_id: UUID
    status: str


class GetExampleHandler:
    def __init__(self, repository: ExampleRepository) -> None:
        self._repository = repository

    async def handle(self, query: GetExampleQuery) -> ExampleStatusDTO:
        if not await self._repository.exists(query.item_id):
            raise NotFoundError(
                code="document_not_found",
                message="Document not found.",
            )
        return ExampleStatusDTO(item_id=query.item_id, status="ok")
