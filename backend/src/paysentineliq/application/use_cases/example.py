from uuid import UUID

from paysentineliq.application.ports.unit_of_work import UnitOfWork
from paysentineliq.domain.errors import NotFoundError


class ExampleService:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def check(self, item_id: UUID) -> bool:
        async with self._unit_of_work as uow:
            found = await uow.examples.exists(item_id)
            await uow.commit()

        if not found:
            raise NotFoundError(
                code="document_not_found",
                message="Document not found.",
            )
        return True
