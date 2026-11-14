import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_async_session_executes_query() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)

    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
    finally:
        await engine.dispose()
