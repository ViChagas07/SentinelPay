from datetime import date
from decimal import Decimal

from paysentineliq.domain.payslip.regulatory import (
    CltData,
    CltParameter,
    InssBracket,
    InssData,
    InssTable,
    IrrfBracket,
    IrrfData,
    IrrfTable,
    MinimumWageData,
    MinimumWageValue,
    RegulatoryTables,
)

SYNTHETIC_SOURCE = "tests/fixtures/synthetic"


def synthetic_inss_table() -> InssTable:
    return InssTable(
        source=f"{SYNTHETIC_SOURCE}#inss",
        valid_from=date(2024, 1, 1),
        valid_until=date(2024, 12, 31),
        salary_cap=Decimal("3000.00"),
        brackets=(
            InssBracket(up_to=Decimal("1000.00"), rate=Decimal("0.10")),
            InssBracket(up_to=Decimal("2000.00"), rate=Decimal("0.20")),
            InssBracket(up_to=None, rate=Decimal("0.30")),
        ),
    )


def synthetic_irrf_table() -> IrrfTable:
    return IrrfTable(
        source=f"{SYNTHETIC_SOURCE}#irrf",
        valid_from=date(2024, 1, 1),
        valid_until=date(2024, 12, 31),
        brackets=(
            IrrfBracket(
                up_to=Decimal("1000.00"),
                rate=Decimal("0.00"),
                deduction=Decimal("0.00"),
            ),
            IrrfBracket(
                up_to=Decimal("2000.00"),
                rate=Decimal("0.10"),
                deduction=Decimal("100.00"),
            ),
            IrrfBracket(
                up_to=None,
                rate=Decimal("0.20"),
                deduction=Decimal("300.00"),
            ),
        ),
    )


def synthetic_regulatory_tables() -> RegulatoryTables:
    return RegulatoryTables(
        inss=InssData(
            version="synthetic-inss",
            source=SYNTHETIC_SOURCE,
            tables=(synthetic_inss_table(),),
        ),
        irrf=IrrfData(
            version="synthetic-irrf",
            source=SYNTHETIC_SOURCE,
            tables=(synthetic_irrf_table(),),
        ),
        minimum_wage=MinimumWageData(
            version="synthetic-minimum",
            source=SYNTHETIC_SOURCE,
            values=(
                MinimumWageValue(
                    source=f"{SYNTHETIC_SOURCE}#minimum",
                    valid_from=date(2024, 1, 1),
                    valid_until=date(2024, 12, 31),
                    value=Decimal("1000.00"),
                ),
            ),
        ),
        clt=CltData(
            version="synthetic-clt",
            source=SYNTHETIC_SOURCE,
            parameters=(
                CltParameter(
                    id="overtime_minimum_percent",
                    source=f"{SYNTHETIC_SOURCE}#clt",
                    valid_from=date(2024, 1, 1),
                    valid_until=date(2024, 12, 31),
                    value=Decimal("0.50"),
                    unit="fraction",
                ),
            ),
        ),
    )
