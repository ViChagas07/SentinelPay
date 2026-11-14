from dataclasses import dataclass
from enum import StrEnum


class DvAlgorithm(StrEnum):
    MOD10 = "mod10"
    MOD11 = "mod11"


@dataclass(frozen=True, slots=True)
class DvError:
    field: str
    expected: int
    actual: int
    algorithm: DvAlgorithm
    source: str
