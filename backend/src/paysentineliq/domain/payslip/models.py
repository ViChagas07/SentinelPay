from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from paysentineliq.domain.boleto.tax_id import Cnpj


class ItemKind(StrEnum):
    EARNING = "earning"
    DEDUCTION = "deduction"
    INFO = "info"
    UNKNOWN = "unknown"


class ItemCategory(StrEnum):
    BASE_SALARY = "base_salary"
    OVERTIME = "overtime"
    INSS = "inss"
    IRRF = "irrf"
    FGTS = "fgts"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class YearMonth:
    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= self.year <= 9999:
            raise ValueError("year must be between 1 and 9999")
        if not 1 <= self.month <= 12:
            raise ValueError("month must be between 1 and 12")

    @property
    def first_day(self) -> date:
        return date(self.year, self.month, 1)

    def __str__(self) -> str:
        return f"{self.month:02d}/{self.year:04d}"


@dataclass(frozen=True, slots=True)
class PayslipItem:
    description: str
    kind: ItemKind
    category: ItemCategory
    amount: Decimal
    overtime_percent: Decimal | None = None
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.amount.is_finite():
            raise ValueError("amount must be finite")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.overtime_percent is not None:
            if not self.overtime_percent.is_finite():
                raise ValueError("overtime_percent must be finite")
            if self.overtime_percent < 0:
                raise ValueError("overtime_percent must be non-negative")

    @property
    def is_earning(self) -> bool:
        return self.kind is ItemKind.EARNING

    @property
    def is_deduction(self) -> bool:
        return self.kind is ItemKind.DEDUCTION


@dataclass(frozen=True, slots=True)
class Payslip:
    employer_name: str | None
    employer_cnpj: Cnpj | None
    employee_name: str | None
    employee_cpf_masked: str | None
    employee_cpf_valid: bool | None
    competency: YearMonth | None
    items: tuple[PayslipItem, ...]
    total_earnings: Decimal | None
    total_deductions: Decimal | None
    net: Decimal | None
    irrf_base: Decimal | None
    dependents: int | None

    def __post_init__(self) -> None:
        for value in (
            self.total_earnings,
            self.total_deductions,
            self.net,
            self.irrf_base,
        ):
            if value is not None and not value.is_finite():
                raise ValueError("monetary values must be finite")
        if self.dependents is not None and self.dependents < 0:
            raise ValueError("dependents must be non-negative")

    @property
    def earning_items(self) -> tuple[PayslipItem, ...]:
        return tuple(item for item in self.items if item.kind is ItemKind.EARNING)

    @property
    def deduction_items(self) -> tuple[PayslipItem, ...]:
        return tuple(item for item in self.items if item.kind is ItemKind.DEDUCTION)

    @property
    def earnings_sum(self) -> Decimal:
        return sum((item.amount for item in self.earning_items), Decimal("0.00"))

    @property
    def deductions_sum(self) -> Decimal:
        return sum((item.amount for item in self.deduction_items), Decimal("0.00"))
