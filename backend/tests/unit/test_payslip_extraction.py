from decimal import Decimal

import pytest

from paysentineliq.domain.payslip.extraction import extract_payslip_fields
from paysentineliq.domain.payslip.models import ItemCategory, ItemKind, YearMonth
from tests.support.payslip_factory import SyntheticPayslip

pytestmark = pytest.mark.unit


def test_extracts_valid_synthetic_payslip() -> None:
    fields = extract_payslip_fields(SyntheticPayslip().ocr_text())

    assert fields.employer_name is not None
    assert fields.employer_name.value == "PAGAMENTOS SINTETICOS LTDA"
    assert fields.employer_cnpj is not None
    assert fields.employer_cnpj.value.digits == "11222333000181"
    assert fields.employee_name is not None
    assert fields.employee_name.value == "CLIENTE SINTETICO"
    assert fields.employee_cpf is not None
    assert fields.employee_cpf.value.digits == "12345678909"
    assert fields.competency is not None
    assert fields.competency.value == YearMonth(2024, 5)
    assert fields.total_earnings is not None
    assert fields.total_earnings.value == Decimal("2100.00")
    assert fields.total_deductions is not None
    assert fields.total_deductions.value == Decimal("380.00")
    assert fields.net is not None
    assert fields.net.value == Decimal("1720.00")
    assert fields.irrf_base is not None
    assert fields.irrf_base.value == Decimal("1800.00")
    assert fields.layout_recognized
    assert fields.layout_confidence == 1.0

    categories = {(item.category, item.kind) for item in fields.items}
    assert (ItemCategory.BASE_SALARY, ItemKind.EARNING) in categories
    assert (ItemCategory.OVERTIME, ItemKind.EARNING) in categories
    assert (ItemCategory.INSS, ItemKind.DEDUCTION) in categories
    assert (ItemCategory.IRRF, ItemKind.DEDUCTION) in categories
    overtime = next(item for item in fields.items if item.category is ItemCategory.OVERTIME)
    assert overtime.amount == Decimal("100.00")
    assert overtime.overtime_percent == Decimal("0.50")


def test_normalizes_ocr_confusions_in_amounts() -> None:
    text = (
        SyntheticPayslip()
        .ocr_text()
        .replace("2.000,00", "2.OOO,OO")
        .replace(
            "100,00",
            "1OO,OO",
        )
    )

    fields = extract_payslip_fields(text)

    base = next(item for item in fields.items if item.category is ItemCategory.BASE_SALARY)
    overtime = next(item for item in fields.items if item.category is ItemCategory.OVERTIME)
    assert base.amount == Decimal("2000.00")
    assert overtime.amount == Decimal("100.00")
    assert base.confidence < 1.0
    assert overtime.confidence < 1.0


def test_unknown_layout_has_low_confidence_without_error() -> None:
    text = "\n".join(
        [
            "2.000,00",
            "100,00",
            "2.100,00",
            "300,00",
            "80,00",
            "380,00",
            "1.720,00",
        ],
    )

    fields = extract_payslip_fields(text)

    assert not fields.layout_recognized
    assert fields.layout_confidence < 0.5
    assert fields.total_earnings is None


@pytest.mark.parametrize("value", ["05/2024", "2024-05", "MAIO/2024"])
def test_extracts_competency_formats(value: str) -> None:
    text = SyntheticPayslip(competency=value).ocr_text()

    fields = extract_payslip_fields(text)

    assert fields.competency is not None
    assert fields.competency.value == YearMonth(2024, 5)
    assert fields.competency.confidence >= 0.9


def test_missing_identity_fields_are_none() -> None:
    text = "\n".join(
        line
        for line in SyntheticPayslip().ocr_text().splitlines()
        if not line.startswith(("CNPJ:", "CPF:", "COMPETENCIA:"))
    )

    fields = extract_payslip_fields(text)

    assert fields.employer_cnpj is None
    assert fields.employee_cpf is None
    assert fields.competency is None


def test_preserves_three_decimal_amounts_for_rounding_rule() -> None:
    text = SyntheticPayslip(overtime_amount="100,005").ocr_text()

    fields = extract_payslip_fields(text)

    overtime = next(item for item in fields.items if item.category is ItemCategory.OVERTIME)
    assert overtime.amount == Decimal("100.005")


def test_duplicate_items_are_extracted() -> None:
    text = (
        SyntheticPayslip()
        .ocr_text()
        .replace(
            "001 SALARIO BASE 2.000,00",
            "001 SALARIO BASE 2.000,00\n001 SALARIO BASE 2.000,00",
        )
    )

    fields = extract_payslip_fields(text)

    base_items = [item for item in fields.items if item.category is ItemCategory.BASE_SALARY]
    assert len(base_items) == 2
