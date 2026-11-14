from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ReadinessStatus:
    database: bool
    cache: bool


class ReadinessChecker(Protocol):
    async def check(self) -> ReadinessStatus: ...
