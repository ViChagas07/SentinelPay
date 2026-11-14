from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from paysentineliq.infrastructure.db.repositories.documents import (
    SqlAlchemyDocumentReadRepository,
)

pytestmark = pytest.mark.unit


class FakeSession:
    def __init__(self, value: str | None) -> None:
        self._value = value
        self.statement: Any = None

    async def scalar(self, statement: Any) -> str | None:
        self.statement = statement
        return self._value


async def test_read_repository_selects_only_s3_key_and_filters_owner() -> None:
    session = FakeSession("users/owner/receipt/analysis/original.pdf")
    repository = SqlAlchemyDocumentReadRepository(cast(AsyncSession, session))

    location = await repository.get_download_location(uuid4(), uuid4())

    assert location is not None
    assert location.s3_key == "users/owner/receipt/analysis/original.pdf"
    sql = str(session.statement)
    assert "documents.s3_key" in sql
    assert "documents.id" in sql
    assert "documents.owner_id" in sql
    assert "documents.kind" not in sql
    assert "documents.sha256" not in sql


async def test_read_repository_returns_none_for_other_owner() -> None:
    session = FakeSession(None)
    repository = SqlAlchemyDocumentReadRepository(cast(AsyncSession, session))

    location = await repository.get_download_location(uuid4(), uuid4())

    assert location is None
