from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from sqlalchemy import Engine, event
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass
class QueryCounter:
    statements: list[str] = field(default_factory=list)
    selects: list[str] = field(default_factory=list)

    @property
    def select_count(self) -> int:
        return len(self.selects)

    def reset(self) -> None:
        self.statements.clear()
        self.selects.clear()

    def record(
        self,
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        self.statements.append(statement)
        if statement.lstrip().upper().startswith("SELECT"):
            self.selects.append(statement)


@contextmanager
def count_queries(engine: Engine | AsyncEngine) -> Iterator[QueryCounter]:
    sync_engine = engine.sync_engine if isinstance(engine, AsyncEngine) else engine
    counter = QueryCounter()
    event.listen(sync_engine, "before_cursor_execute", counter.record)
    try:
        yield counter
    finally:
        event.remove(sync_engine, "before_cursor_execute", counter.record)
