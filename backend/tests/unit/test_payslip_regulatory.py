from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from paysentineliq.domain.payslip.regulatory import load_regulatory_tables

pytestmark = pytest.mark.unit

_EMPTY_INSS: dict[str, Any] = {
    "versao": "inss-test",
    "fonte": "tests/fixtures/synthetic",
    "vigencia_inicio": None,
    "vigencia_fim": None,
    "tabelas": [],
}
_EMPTY_IRRF: dict[str, Any] = {
    "versao": "irrf-test",
    "fonte": "tests/fixtures/synthetic",
    "vigencia_inicio": None,
    "vigencia_fim": None,
    "tabelas": [],
}
_EMPTY_MINIMUM: dict[str, Any] = {
    "versao": "minimum-test",
    "fonte": "tests/fixtures/synthetic",
    "vigencia_inicio": None,
    "vigencia_fim": None,
    "valores": [],
}
_EMPTY_CLT: dict[str, Any] = {
    "versao": "clt-test",
    "fonte": "tests/fixtures/synthetic",
    "vigencia_inicio": None,
    "vigencia_fim": None,
    "parametros": [],
}


def _write(root: Path, name: str, payload: dict[str, Any]) -> None:
    (root / name).write_text(
        yaml.safe_dump(payload, allow_unicode=True),
        encoding="utf-8",
    )


def test_default_files_are_empty_and_marked_not_verifiable() -> None:
    tables = load_regulatory_tables()

    assert tables.inss.version == "inss-v1"
    assert tables.inss.tables == ()
    assert "NAO VERIFICAVEL" in tables.inss.source
    assert tables.irrf.tables == ()
    assert tables.minimum_wage.values == ()
    assert tables.clt.parameters == ()
    assert tables.inss.for_date(date(2024, 5, 1)) is None
    assert tables.irrf.for_date(date(2024, 5, 1)) is None
    assert tables.minimum_wage.for_date(date(2024, 5, 1)) is None
    assert tables.clt.parameter_for("overtime_minimum_percent", date(2024, 5, 1)) is None


def test_loader_reads_synthetic_inss_table_and_converts_decimal(tmp_path: Path) -> None:
    inss = {
        "versao": "inss-test",
        "fonte": "tests/fixtures/synthetic",
        "vigencia_inicio": None,
        "vigencia_fim": None,
        "tabelas": [
            {
                "fonte": "tests/fixtures/synthetic#inss",
                "vigencia_inicio": "2024-01-01",
                "vigencia_fim": "2024-12-31",
                "teto_salario": "3000.00",
                "faixas": [
                    {"ate": "1000.00", "aliquota": "0.10"},
                    {"ate": "2000.00", "aliquota": "0.20"},
                    {"ate": None, "aliquota": "0.30"},
                ],
            },
        ],
    }
    _write(tmp_path, "inss.yaml", inss)
    _write(tmp_path, "irrf.yaml", _EMPTY_IRRF)
    _write(tmp_path, "salario_minimo.yaml", _EMPTY_MINIMUM)
    _write(tmp_path, "clt.yaml", _EMPTY_CLT)

    tables = load_regulatory_tables(tmp_path)

    table = tables.inss.for_date(date(2024, 5, 1))
    assert table is not None
    assert table.source == "tests/fixtures/synthetic#inss"
    assert table.salary_cap is not None
    assert str(table.salary_cap) == "3000.00"
    assert len(table.brackets) == 3
    assert str(table.brackets[0].rate) == "0.10"
    assert tables.inss.for_date(date(2025, 1, 1)) is None


def test_lookup_respects_validity_window_and_open_ended_table(tmp_path: Path) -> None:
    minimum = {
        "versao": "minimum-test",
        "fonte": "tests/fixtures/synthetic",
        "vigencia_inicio": None,
        "vigencia_fim": None,
        "valores": [
            {
                "fonte": "tests/fixtures/synthetic#minimum-2024",
                "vigencia_inicio": "2024-01-01",
                "vigencia_fim": "2024-12-31",
                "valor": "1000.00",
            },
            {
                "fonte": "tests/fixtures/synthetic#minimum-2025",
                "vigencia_inicio": "2025-01-01",
                "vigencia_fim": None,
                "valor": "1100.00",
            },
        ],
    }
    _write(tmp_path, "inss.yaml", _EMPTY_INSS)
    _write(tmp_path, "irrf.yaml", _EMPTY_IRRF)
    _write(tmp_path, "salario_minimo.yaml", minimum)
    _write(tmp_path, "clt.yaml", _EMPTY_CLT)

    tables = load_regulatory_tables(tmp_path)

    first = tables.minimum_wage.for_date(date(2024, 6, 1))
    second = tables.minimum_wage.for_date(date(2025, 6, 1))
    assert first is not None
    assert str(first.value) == "1000.00"
    assert second is not None
    assert str(second.value) == "1100.00"
    assert tables.minimum_wage.for_date(date(2023, 12, 1)) is None


def test_loader_reads_clt_parameter(tmp_path: Path) -> None:
    clt = {
        "versao": "clt-test",
        "fonte": "tests/fixtures/synthetic",
        "vigencia_inicio": None,
        "vigencia_fim": None,
        "parametros": [
            {
                "id": "overtime_minimum_percent",
                "fonte": "tests/fixtures/synthetic#clt",
                "vigencia_inicio": "2024-01-01",
                "vigencia_fim": None,
                "valor": "0.50",
                "unidade": "fraction",
            },
        ],
    }
    _write(tmp_path, "inss.yaml", _EMPTY_INSS)
    _write(tmp_path, "irrf.yaml", _EMPTY_IRRF)
    _write(tmp_path, "salario_minimo.yaml", _EMPTY_MINIMUM)
    _write(tmp_path, "clt.yaml", clt)

    tables = load_regulatory_tables(tmp_path)

    parameter = tables.clt.parameter_for("overtime_minimum_percent", date(2024, 5, 1))
    assert parameter is not None
    assert str(parameter.value) == "0.50"
    assert parameter.unit == "fraction"
    assert tables.clt.parameter_for("unknown", date(2024, 5, 1)) is None


@pytest.mark.parametrize(
    "inss_override",
    [
        {
            "tabelas": [
                {
                    "vigencia_inicio": "2024-01-01",
                    "faixas": [{"ate": "1000.00", "aliquota": "0.10"}],
                },
            ],
        },
        {
            "tabelas": [
                {
                    "fonte": "tests/fixtures/synthetic",
                    "vigencia_inicio": "not-a-date",
                    "faixas": [{"ate": "1000.00", "aliquota": "0.10"}],
                },
            ],
        },
        {
            "tabelas": [
                {
                    "fonte": "tests/fixtures/synthetic",
                    "vigencia_inicio": "2024-01-01",
                    "faixas": [{"ate": "1000.00", "aliquota": "1.10"}],
                },
            ],
        },
        {
            "tabelas": [
                {
                    "fonte": "tests/fixtures/synthetic",
                    "vigencia_inicio": "2024-01-01",
                    "faixas": [
                        {"ate": "2000.00", "aliquota": "0.10"},
                        {"ate": "1000.00", "aliquota": "0.20"},
                    ],
                },
            ],
        },
    ],
)
def test_loader_rejects_invalid_inss_schema(
    tmp_path: Path,
    inss_override: dict[str, Any],
) -> None:
    inss = {**_EMPTY_INSS, **inss_override}
    _write(tmp_path, "inss.yaml", inss)
    _write(tmp_path, "irrf.yaml", _EMPTY_IRRF)
    _write(tmp_path, "salario_minimo.yaml", _EMPTY_MINIMUM)
    _write(tmp_path, "clt.yaml", _EMPTY_CLT)

    with pytest.raises(ValueError):
        load_regulatory_tables(tmp_path)
