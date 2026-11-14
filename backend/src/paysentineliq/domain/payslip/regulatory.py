from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Protocol, TypeVar

import yaml

_DEFAULT_DATA_DIR = Path(__file__).with_name("data") / "regulatory"


@dataclass(frozen=True, slots=True)
class InssBracket:
    up_to: Decimal | None
    rate: Decimal


@dataclass(frozen=True, slots=True)
class InssTable:
    source: str
    valid_from: date
    valid_until: date | None
    salary_cap: Decimal | None
    brackets: tuple[InssBracket, ...]


@dataclass(frozen=True, slots=True)
class IrrfBracket:
    up_to: Decimal | None
    rate: Decimal
    deduction: Decimal


@dataclass(frozen=True, slots=True)
class IrrfTable:
    source: str
    valid_from: date
    valid_until: date | None
    brackets: tuple[IrrfBracket, ...]


@dataclass(frozen=True, slots=True)
class MinimumWageValue:
    source: str
    valid_from: date
    valid_until: date | None
    value: Decimal


@dataclass(frozen=True, slots=True)
class CltParameter:
    id: str
    source: str
    valid_from: date
    valid_until: date | None
    value: Decimal
    unit: str


class _Dated(Protocol):
    @property
    def valid_from(self) -> date: ...

    @property
    def valid_until(self) -> date | None: ...


T = TypeVar("T", bound=_Dated)


def _select_by_date(tables: tuple[T, ...], value: date) -> T | None:
    matches = [
        table
        for table in tables
        if table.valid_from <= value and (table.valid_until is None or value <= table.valid_until)
    ]
    if not matches:
        return None
    return max(matches, key=lambda table: table.valid_from)


@dataclass(frozen=True, slots=True)
class InssData:
    version: str
    source: str
    tables: tuple[InssTable, ...]

    def for_date(self, value: date) -> InssTable | None:
        return _select_by_date(self.tables, value)


@dataclass(frozen=True, slots=True)
class IrrfData:
    version: str
    source: str
    tables: tuple[IrrfTable, ...]

    def for_date(self, value: date) -> IrrfTable | None:
        return _select_by_date(self.tables, value)


@dataclass(frozen=True, slots=True)
class MinimumWageData:
    version: str
    source: str
    values: tuple[MinimumWageValue, ...]

    def for_date(self, value: date) -> MinimumWageValue | None:
        return _select_by_date(self.values, value)


@dataclass(frozen=True, slots=True)
class CltData:
    version: str
    source: str
    parameters: tuple[CltParameter, ...]

    def parameter_for(self, parameter_id: str, value: date) -> CltParameter | None:
        return _select_by_date(
            tuple(item for item in self.parameters if item.id == parameter_id),
            value,
        )


@dataclass(frozen=True, slots=True)
class RegulatoryTables:
    inss: InssData
    irrf: IrrfData
    minimum_wage: MinimumWageData
    clt: CltData


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        payload: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot read regulatory data {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"regulatory data {path} must be a mapping")
    return payload


def _string(payload: dict[str, Any], key: str, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{key} must be a non-empty string")
    return value


def _optional_date(payload: dict[str, Any], key: str, context: str) -> date | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{context}.{key} must be an ISO date") from exc
    raise ValueError(f"{context}.{key} must be an ISO date or null")


def _required_date(payload: dict[str, Any], key: str, context: str) -> date:
    value = _optional_date(payload, key, context)
    if value is None:
        raise ValueError(f"{context}.{key} is required")
    return value


def _decimal(payload: dict[str, Any], key: str, context: str) -> Decimal:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(
            f"{context}.{key} must be a string decimal to avoid binary float",
        )
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{context}.{key} must be a decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{context}.{key} must be finite")
    return result


def _non_negative(value: Decimal, context: str) -> Decimal:
    if value < 0:
        raise ValueError(f"{context} must be non-negative")
    return value


def _rate(payload: dict[str, Any], key: str, context: str) -> Decimal:
    value = _non_negative(_decimal(payload, key, context), f"{context}.{key}")
    if value > 1:
        raise ValueError(f"{context}.{key} must be between 0 and 1")
    return value


def _list(payload: dict[str, Any], key: str, context: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{context}.{key} must be a list")
    return value


def _mapping_list(
    payload: dict[str, Any],
    key: str,
    context: str,
) -> list[dict[str, Any]]:
    items = _list(payload, key, context)
    result: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{context}.{key}[{index}] must be a mapping")
        result.append(item)
    return result


def _load_inss(path: Path) -> InssData:
    payload = _read_yaml(path)
    tables: list[InssTable] = []
    for index, raw_table in enumerate(_mapping_list(payload, "tabelas", path.name)):
        context = f"{path.name}.tabelas[{index}]"
        brackets_raw = _mapping_list(raw_table, "faixas", context)
        if not brackets_raw:
            raise ValueError(f"{context}.faixas must not be empty")
        brackets: list[InssBracket] = []
        previous: Decimal | None = None
        for bracket_index, raw_bracket in enumerate(brackets_raw):
            bracket_context = f"{context}.faixas[{bracket_index}]"
            up_to = (
                None
                if raw_bracket.get("ate") is None
                else _non_negative(
                    _decimal(raw_bracket, "ate", bracket_context),
                    f"{bracket_context}.ate",
                )
            )
            if up_to is None and bracket_index != len(brackets_raw) - 1:
                raise ValueError(f"{bracket_context}.ate can be null only at the end")
            if up_to is not None and previous is not None and up_to <= previous:
                raise ValueError(f"{bracket_context}.ate must be increasing")
            if up_to is not None:
                previous = up_to
            brackets.append(
                InssBracket(
                    up_to=up_to,
                    rate=_rate(raw_bracket, "aliquota", bracket_context),
                ),
            )
        salary_cap_raw = raw_table.get("teto_salario")
        salary_cap = (
            None
            if salary_cap_raw is None
            else _non_negative(
                _decimal(raw_table, "teto_salario", context),
                f"{context}.teto_salario",
            )
        )
        tables.append(
            InssTable(
                source=_string(raw_table, "fonte", context),
                valid_from=_required_date(raw_table, "vigencia_inicio", context),
                valid_until=_optional_date(raw_table, "vigencia_fim", context),
                salary_cap=salary_cap,
                brackets=tuple(brackets),
            ),
        )
    return InssData(
        version=_string(payload, "versao", path.name),
        source=_string(payload, "fonte", path.name),
        tables=tuple(tables),
    )


def _load_irrf(path: Path) -> IrrfData:
    payload = _read_yaml(path)
    tables: list[IrrfTable] = []
    for index, raw_table in enumerate(_mapping_list(payload, "tabelas", path.name)):
        context = f"{path.name}.tabelas[{index}]"
        brackets_raw = _mapping_list(raw_table, "faixas", context)
        if not brackets_raw:
            raise ValueError(f"{context}.faixas must not be empty")
        brackets: list[IrrfBracket] = []
        previous: Decimal | None = None
        for bracket_index, raw_bracket in enumerate(brackets_raw):
            bracket_context = f"{context}.faixas[{bracket_index}]"
            up_to = (
                None
                if raw_bracket.get("ate") is None
                else _non_negative(
                    _decimal(raw_bracket, "ate", bracket_context),
                    f"{bracket_context}.ate",
                )
            )
            if up_to is None and bracket_index != len(brackets_raw) - 1:
                raise ValueError(f"{bracket_context}.ate can be null only at the end")
            if up_to is not None and previous is not None and up_to <= previous:
                raise ValueError(f"{bracket_context}.ate must be increasing")
            if up_to is not None:
                previous = up_to
            brackets.append(
                IrrfBracket(
                    up_to=up_to,
                    rate=_rate(raw_bracket, "aliquota", bracket_context),
                    deduction=_non_negative(
                        _decimal(raw_bracket, "deducao", bracket_context),
                        f"{bracket_context}.deducao",
                    ),
                ),
            )
        tables.append(
            IrrfTable(
                source=_string(raw_table, "fonte", context),
                valid_from=_required_date(raw_table, "vigencia_inicio", context),
                valid_until=_optional_date(raw_table, "vigencia_fim", context),
                brackets=tuple(brackets),
            ),
        )
    return IrrfData(
        version=_string(payload, "versao", path.name),
        source=_string(payload, "fonte", path.name),
        tables=tuple(tables),
    )


def _load_minimum_wage(path: Path) -> MinimumWageData:
    payload = _read_yaml(path)
    values: list[MinimumWageValue] = []
    for index, raw_value in enumerate(_mapping_list(payload, "valores", path.name)):
        context = f"{path.name}.valores[{index}]"
        values.append(
            MinimumWageValue(
                source=_string(raw_value, "fonte", context),
                valid_from=_required_date(raw_value, "vigencia_inicio", context),
                valid_until=_optional_date(raw_value, "vigencia_fim", context),
                value=_non_negative(
                    _decimal(raw_value, "valor", context),
                    f"{context}.valor",
                ),
            ),
        )
    return MinimumWageData(
        version=_string(payload, "versao", path.name),
        source=_string(payload, "fonte", path.name),
        values=tuple(values),
    )


def _load_clt(path: Path) -> CltData:
    payload = _read_yaml(path)
    parameters: list[CltParameter] = []
    for index, raw_parameter in enumerate(
        _mapping_list(payload, "parametros", path.name),
    ):
        context = f"{path.name}.parametros[{index}]"
        parameters.append(
            CltParameter(
                id=_string(raw_parameter, "id", context),
                source=_string(raw_parameter, "fonte", context),
                valid_from=_required_date(raw_parameter, "vigencia_inicio", context),
                valid_until=_optional_date(raw_parameter, "vigencia_fim", context),
                value=_non_negative(
                    _decimal(raw_parameter, "valor", context),
                    f"{context}.valor",
                ),
                unit=_string(raw_parameter, "unidade", context),
            ),
        )
    return CltData(
        version=_string(payload, "versao", path.name),
        source=_string(payload, "fonte", path.name),
        parameters=tuple(parameters),
    )


def load_regulatory_tables(root: Path | None = None) -> RegulatoryTables:
    base = root if root is not None else _DEFAULT_DATA_DIR
    return RegulatoryTables(
        inss=_load_inss(base / "inss.yaml"),
        irrf=_load_irrf(base / "irrf.yaml"),
        minimum_wage=_load_minimum_wage(base / "salario_minimo.yaml"),
        clt=_load_clt(base / "clt.yaml"),
    )
