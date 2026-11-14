from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Money:
    cents: int

    def __post_init__(self) -> None:
        if self.cents < 0:
            raise ValueError("cents must be non-negative")

    @property
    def as_decimal(self) -> Decimal:
        return Decimal(self.cents).scaleb(-2)

    @classmethod
    def from_decimal(cls, value: Decimal) -> "Money":
        scaled = value * 100
        if scaled != scaled.to_integral_value():
            raise ValueError("value must have at most two decimal places")
        cents = int(scaled)
        if cents < 0:
            raise ValueError("value must be non-negative")
        return cls(cents)
