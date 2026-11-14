from datetime import date
from decimal import Decimal

import pytest

from paysentineliq.domain.boleto.bank_directory import Bank, BankDirectory
from paysentineliq.domain.boleto.due_date import (
    due_date_from_factor,
    factor_from_due_date,
)
from paysentineliq.domain.boleto.dv import DvAlgorithm
from paysentineliq.domain.boleto.errors import NotVerifiableLayoutError
from paysentineliq.domain.boleto.lines import (
    BankDigitableLine,
    Barcode,
    UtilityDigitableLine,
)
from paysentineliq.domain.boleto.money import Money
from paysentineliq.domain.boleto.sources import MANUAL_FEBRABAN
from tests.support.boleto_factory import build_boleto, decimal_value

EMPTY_DIRECTORY = BankDirectory(banks=(), version="empty", sources=())
BRADESCO_DIRECTORY = BankDirectory(
    banks=(
        Bank(
            code="237",
            name="Banco Bradesco S.A.",
            aliases=(),
            field_dv={3: DvAlgorithm.MOD11},
            source="knowledge/layouts/boleto_bradesco.pdf",
        ),
    ),
    version="test",
    sources=("knowledge/layouts/boleto_bradesco.pdf",),
)


def test_valid_line_converts_to_barcode_and_back() -> None:
    boleto = build_boleto()
    line = BankDigitableLine(boleto.line)
    barcode = Barcode(boleto.barcode)

    assert line.to_barcode() == barcode
    assert barcode.to_line(EMPTY_DIRECTORY) == line
    assert line.bank_code == "341"
    assert line.currency == "9"
    assert line.due_factor == 9000
    assert line.amount_cents == 123456
    assert line.free_field == boleto.free_field
    assert line.general_dv == boleto.barcode[4]
    assert barcode.bank_code == "341"
    assert barcode.due_factor == 9000
    assert barcode.amount_cents == 123456
    assert barcode.free_field == boleto.free_field


def test_valid_line_has_no_dv_errors() -> None:
    boleto = build_boleto()
    line = BankDigitableLine(boleto.line)
    barcode = Barcode(boleto.barcode)

    assert line.dv_errors(EMPTY_DIRECTORY) == ()
    assert barcode.dv_errors(EMPTY_DIRECTORY) == ()
    assert barcode.general_dv_is_valid()


def test_field_dv_tampering_is_reported() -> None:
    boleto = build_boleto()
    digits = boleto.line
    tampered = digits[:9] + str((int(digits[9]) + 1) % 10) + digits[10:]

    errors = BankDigitableLine(tampered).dv_errors(EMPTY_DIRECTORY)

    assert len(errors) == 1
    assert errors[0].field == "1"
    assert errors[0].expected == 4
    assert errors[0].actual == 5
    assert errors[0].algorithm is DvAlgorithm.MOD10
    assert errors[0].source == MANUAL_FEBRABAN


def test_general_dv_tampering_is_reported() -> None:
    boleto = build_boleto()
    digits = boleto.line
    tampered = digits[:32] + str((int(digits[32]) + 1) % 10) + digits[33:]

    line = BankDigitableLine(tampered)

    errors = line.dv_errors(EMPTY_DIRECTORY)
    assert len(errors) == 1
    assert errors[0].field == "general"
    assert errors[0].algorithm is DvAlgorithm.MOD11
    assert not line.to_barcode().general_dv_is_valid()


def test_bradesco_field_three_uses_mod11() -> None:
    boleto = build_boleto(bank="237")
    line = BankDigitableLine(boleto.line)

    assert line.dv_errors(BRADESCO_DIRECTORY) == ()

    errors = line.dv_errors(EMPTY_DIRECTORY)
    assert len(errors) == 1
    assert errors[0].field == "3"
    assert errors[0].algorithm is DvAlgorithm.MOD10


def test_other_banks_keep_mod10_field_three() -> None:
    boleto = build_boleto(bank="341")
    line = BankDigitableLine(boleto.line)

    assert line.dv_errors(BRADESCO_DIRECTORY) == ()


@pytest.mark.parametrize(
    "digits",
    ["", "1" * 46, "1" * 48, "A" * 47, "3419123454678901234576789012345779000000012345X"],
)
def test_bank_line_rejects_invalid_structure(digits: str) -> None:
    with pytest.raises(ValueError):
        BankDigitableLine(digits)


@pytest.mark.parametrize("digits", ["", "1" * 43, "1" * 45, "9" * 43 + "X"])
def test_barcode_rejects_invalid_structure(digits: str) -> None:
    with pytest.raises(ValueError):
        Barcode(digits)


def test_utility_line_is_structurally_valid_but_not_convertible() -> None:
    line = UtilityDigitableLine("9" * 48)

    assert line.digits == "9" * 48

    with pytest.raises(NotVerifiableLayoutError):
        line.to_barcode()

    with pytest.raises(ValueError):
        UtilityDigitableLine("9" * 47)


def test_due_date_factor_cycle_follows_documented_formula() -> None:
    assert due_date_from_factor(0) is None
    assert due_date_from_factor(9999) == date(2025, 2, 21)
    assert due_date_from_factor(1) == date(1997, 10, 8)
    assert factor_from_due_date(None) == 0
    assert factor_from_due_date(date(2025, 2, 21)) == 9999


@pytest.mark.parametrize("factor", [-1, 10000])
def test_due_date_factor_rejects_out_of_range(factor: int) -> None:
    with pytest.raises(ValueError):
        due_date_from_factor(factor)


@pytest.mark.parametrize("value", [date(1997, 10, 6), date(2025, 2, 22)])
def test_factor_from_due_date_rejects_out_of_range(value: date) -> None:
    with pytest.raises(ValueError):
        factor_from_due_date(value)


def test_money_keeps_integer_cents() -> None:
    money = Money(123456)

    assert money.cents == 123456
    assert money.as_decimal == Decimal("1234.56")
    assert Money.from_decimal(Decimal("1234.56")) == money
    assert Money.from_decimal(Decimal("0.01")).cents == 1
    assert decimal_value(123456) == Decimal("1234.56")

    with pytest.raises(ValueError):
        Money(-1)
    with pytest.raises(ValueError):
        Money.from_decimal(Decimal("1.234"))


def test_bradesco_barcode_roundtrip_uses_mod11_field_three() -> None:
    boleto = build_boleto(bank="237")
    line = BankDigitableLine(boleto.line)

    assert line.to_barcode().to_line(BRADESCO_DIRECTORY) == line
    assert BRADESCO_DIRECTORY.field_dv_source("237", 3) == "knowledge/layouts/boleto_bradesco.pdf"


def test_money_rejects_negative_decimal() -> None:
    with pytest.raises(ValueError):
        Money.from_decimal(Decimal("-1.00"))


def test_field_access_rejects_unknown_field() -> None:
    line = BankDigitableLine(build_boleto().line)

    with pytest.raises(ValueError):
        line.field_data(4)
    with pytest.raises(ValueError):
        line.field_dv(4)
