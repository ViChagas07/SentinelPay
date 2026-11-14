import pytest

from paysentineliq.domain.boleto.tax_id import Cnpj, Cpf, TaxIdKind, parse_tax_id


def test_valid_cpf_check_digits() -> None:
    cpf = Cpf("12345678909")

    assert cpf.is_valid
    assert cpf.kind is TaxIdKind.CPF
    assert "12345678909" not in cpf.masked


def test_invalid_cpf_check_digits() -> None:
    assert not Cpf("12345678908").is_valid
    assert not Cpf("11111111111").is_valid
    assert not Cpf("00000000000").is_valid


def test_valid_cnpj_check_digits() -> None:
    cnpj = Cnpj("11222333000181")

    assert cnpj.is_valid
    assert cnpj.kind is TaxIdKind.CNPJ
    assert "11222333000181" not in cnpj.masked


def test_invalid_cnpj_check_digits() -> None:
    assert not Cnpj("11222333000180").is_valid
    assert not Cnpj("00000000000000").is_valid
    assert not Cnpj("11111111111111").is_valid


def test_parse_tax_id_accepts_formatted_and_plain_values() -> None:
    cpf = parse_tax_id("CPF: 123.456.789-09")
    cnpj = parse_tax_id("CNPJ: 11.222.333/0001-81")
    plain = parse_tax_id("11222333000181")

    assert isinstance(cpf, Cpf)
    assert cpf.digits == "12345678909"
    assert isinstance(cnpj, Cnpj)
    assert cnpj.digits == "11222333000181"
    assert isinstance(plain, Cnpj)


def test_parse_tax_id_rejects_other_lengths() -> None:
    assert parse_tax_id("123") is None
    assert parse_tax_id("123456789012345") is None
    assert parse_tax_id("") is None


def test_tax_id_rejects_invalid_structure() -> None:
    with pytest.raises(ValueError):
        Cpf("123")
    with pytest.raises(ValueError):
        Cpf("1234567890A")
    with pytest.raises(ValueError):
        Cnpj("123")
