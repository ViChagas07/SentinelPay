import logging
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from paysentineliq.application.queries.example import GetExampleHandler, GetExampleQuery
from paysentineliq.infrastructure.logging import get_request_id
from paysentineliq.interface.api.dependencies import get_example_query, get_locale

router = APIRouter(prefix="/example", tags=["example"])
_logger = logging.getLogger("paysentineliq")


class ExampleResponse(BaseModel):
    item_id: UUID
    status: Literal["ok"]
    locale: str
    request_id: str


@router.get("/{item_id}", response_model=ExampleResponse)
async def example(
    item_id: UUID,
    handler: Annotated[GetExampleHandler, Depends(get_example_query)],
    locale: Annotated[str, Depends(get_locale)],
    emit_log: bool = False,
) -> ExampleResponse:
    if emit_log:
        _logger.info(
            "example_demo email=%s cpf=%s",
            "demo@example.com",
            "123.456.789-00",
        )

    await handler.handle(GetExampleQuery(item_id=item_id))
    return ExampleResponse(
        item_id=item_id,
        status="ok",
        locale=locale,
        request_id=get_request_id(),
    )
