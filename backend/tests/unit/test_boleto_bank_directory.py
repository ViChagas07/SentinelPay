from paysentineliq.domain.boleto.bank_directory import load_bank_directory
from paysentineliq.domain.boleto.dv import DvAlgorithm
from paysentineliq.domain.boleto.sources import ACTIVE_SOURCES


def test_default_bank_directory_comes_from_versioned_data() -> None:
    directory = load_bank_directory()

    assert directory.version == "febraban-banks-v1"
    assert len(directory.banks) == 25
    assert directory.sources


def test_every_bank_has_a_registered_source() -> None:
    directory = load_bank_directory()

    for bank in directory.banks:
        assert bank.source
        assert any(source in bank.source for source in ACTIVE_SOURCES)


def test_directory_finds_banks_by_code_and_name() -> None:
    directory = load_bank_directory()

    by_code = directory.find_by_code("341")
    by_name = directory.find_by_name("BANCO ITAU S.A.  341")
    santander = directory.find_by_name("BANCO SANTANDER S.A.  033")

    assert by_code is not None
    assert by_code.name == "Banco Itaú S.A."
    assert by_name is not None
    assert by_name.code == "341"
    assert santander is not None
    assert santander.code == "033"
    assert directory.find_by_name("texto sem banco") is None
    assert directory.find_by_code("999") is None


def test_bradesco_field_three_override_is_loaded() -> None:
    directory = load_bank_directory()

    bradesco = directory.find_by_code("237")
    assert bradesco is not None
    assert bradesco.field_dv[3] is DvAlgorithm.MOD11
    assert directory.field_dv_algorithm("237", 3) is DvAlgorithm.MOD11
    assert directory.field_dv_algorithm("237", 1) is DvAlgorithm.MOD10
    assert directory.field_dv_algorithm("341", 3) is DvAlgorithm.MOD10
