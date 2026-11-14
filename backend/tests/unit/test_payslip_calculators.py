from decimal import Decimal

import pytest

from paysentineliq.domain.payslip.models import YearMonth
from tests.support.regulatory_factory import (
    synthetic_inss_table,
    synthetic_irrf_table,
    synthetic_regulatory_tables,
)

pytestmark = pytest.mark.unit


def test_inss_progressive_calculation() -> None:
    table = synthetic_inss_table()

    assert table.calculate(Decimal("500.00")) == Decimal("50.00")
    assert table.calculate(Decimal("2500.00")) == Decimal("450.00")
    assert table.calculate(Decimal("3500.00")) == Decimal("600.00")


def test_irrf_calculation() -> None:
    table = synthetic_irrf_table()

    assert table.calculate(Decimal("500.00")) == Decimal("0.00")
    assert table.calculate(Decimal("1000.00")) == Decimal("0.00")
    assert table.calculate(Decimal("1800.00")) == Decimal("80.00")
    assert table.calculate(Decimal("2500.00")) == Decimal("200.00")


def test_regulatory_tables_lookup_by_competency() -> None:
    tables = synthetic_regulatory_tables()
    competency = YearMonth(2024, 5)

    assert tables.inss_for(competency) is not None
    assert tables.irrf_for(competency) is not None
    assert tables.minimum_wage_for(competency) == Decimal("1000.00")
    overtime = tables.clt_parameter_for("overtime_minimum_percent", competency)
    assert overtime is not None
    assert overtime.value == Decimal("0.50")

    assert tables.inss_for(YearMonth(2025, 5)) is None
    assert tables.minimum_wage_for(YearMonth(2025, 5)) is None


def test_calculators_reject_negative_base() -> None:
    with pytest.raises(ValueError):
        synthetic_inss_table().calculate(Decimal("-1.00"))
    with pytest.raises(ValueError):
        synthetic_irrf_table().calculate(Decimal("-1.00"))
