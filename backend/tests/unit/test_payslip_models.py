from decimal import Decimal

import pytest

from paysentineliq.domain.boleto.tax_id import Cnpj
from paysentineliq.domain.payslip.models import (
    ItemCategory,
    ItemKind,
    Payslip,
    PayslipItem,
    YearMonth,
)

pytestmark = pytest.mark.unit


def test_year_month_validates_and_exposes_first_day() -> None:
    competency = YearMonth(2024, 5)

    assert competency.first_day.isoformat() == "2024-05-01"
    assert str(competency) == "05/2024"

    with pytest.raises(ValueError):
        YearMonth(2024, 0)
    with pytest.raises(ValueError):
        YearMonth(2024, 13)


def test_payslip_sums_known_items_and_masks_cpf() -> None:
    items = (
        PayslipItem(
            description="SALARIO BASE",
            kind=ItemKind.EARNING,
            category=ItemCategory.BASE_SALARY,
            amount=Decimal("2000.00"),
        ),
        PayslipItem(
            description="HORAS EXTRAS",
            kind=ItemKind.EARNING,
            category=ItemCategory.OVERTIME,
            amount=Decimal("100.00"),
            overtime_percent=Decimal("0.50"),
        ),
        PayslipItem(
            description="INSS",
            kind=ItemKind.DEDUCTION,
            category=ItemCategory.INSS,
            amount=Decimal("300.00"),
        ),
        PayslipItem(
            description="FGTS",
            kind=ItemKind.INFO,
            category=ItemCategory.FGTS,
            amount=Decimal("168.00"),
        ),
    )
    payslip = Payslip(
        employer_name="PAGAMENTOS SINTETICOS LTDA",
        employer_cnpj=Cnpj("11222333000181"),
        employee_name="CLIENTE SINTETICO",
        employee_cpf_masked="***.***.***-09",
        employee_cpf_valid=True,
        competency=YearMonth(2024, 5),
        items=items,
        total_earnings=Decimal("2100.00"),
        total_deductions=Decimal("300.00"),
        net=Decimal("1800.00"),
        irrf_base=None,
        dependents=0,
    )

    assert payslip.earnings_sum == Decimal("2100.00")
    assert payslip.deductions_sum == Decimal("300.00")
    assert payslip.employee_cpf_masked == "***.***.***-09"
    assert len(payslip.earning_items) == 2
    assert len(payslip.deduction_items) == 1


def test_item_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError):
        PayslipItem(
            description="INSS",
            kind=ItemKind.DEDUCTION,
            category=ItemCategory.INSS,
            amount=Decimal("1.00"),
            confidence=1.5,
        )
