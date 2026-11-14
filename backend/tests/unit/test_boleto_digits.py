import pytest

from paysentineliq.domain.boleto.digits import (
    mod10,
    mod11,
    normalize_ocr_digits,
    only_digits,
)
from tests.support.boleto_factory import build_boleto


def test_mod10_matches_documented_field_examples() -> None:
    assert mod10("341912345") == 4
    assert mod10("6789012345") == 7
    assert mod10("0") == 0


def test_mod11_matches_general_dv_and_zero_remainder_rule() -> None:
    boleto = build_boleto()
    data = boleto.barcode[:4] + boleto.barcode[5:]
    assert mod11(data) == int(boleto.barcode[4])
    assert mod11("0") == 1
    assert mod11("1") == 9


@pytest.mark.parametrize("value", ["", "12A", "1.2"])
def test_dv_functions_reject_non_digits(value: str) -> None:
    with pytest.raises(ValueError):
        mod10(value)
    with pytest.raises(ValueError):
        mod11(value)


def test_normalize_ocr_digits_counts_corrections() -> None:
    normalized = normalize_ocr_digits("3419I2345O")
    assert normalized.text == "3419123450"
    assert normalized.corrections == 2

    untouched = normalize_ocr_digits("AB1")
    assert untouched.text == "AB1"
    assert untouched.corrections == 0


def test_only_digits_removes_separators() -> None:
    assert only_digits("34191.23454 67890-123457") == "341912345467890123457"
