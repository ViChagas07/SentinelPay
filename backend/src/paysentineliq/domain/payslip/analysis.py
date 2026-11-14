import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from paysentineliq.domain.boleto.tax_id import Cnpj
from paysentineliq.domain.payslip.extraction import (
    ExtractedField,
    ExtractedItem,
    PayslipFields,
)
from paysentineliq.domain.payslip.models import (
    ItemCategory,
    ItemKind,
    Payslip,
    PayslipItem,
    YearMonth,
)
from paysentineliq.domain.payslip.regulatory import RegulatoryTables, load_regulatory_tables
from paysentineliq.domain.payslip.rules import (
    CRITICAL_FLOOR,
    RULE_SET_VERSION,
    RULES,
    Evidence,
    EvidenceStatus,
    RuleDefinition,
    Severity,
    active_rules,
)

_CENT = Decimal("0.01")
_TOLERANCE = Decimal("0.01")
_OVERTIME_PARAMETER = "overtime_minimum_percent"


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _normalize_description(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_marks.casefold().split())


def _mask_cnpj(digits: str) -> str:
    return f"**.***.***/****-{digits[-2:]}"


@dataclass(frozen=True, slots=True)
class PayslipAnalysisFields:
    employer_name: ExtractedField[str] | None
    employer_cnpj: ExtractedField[Cnpj] | None
    employee_name: ExtractedField[str] | None
    employee_cpf_masked: ExtractedField[str] | None
    competency: ExtractedField[YearMonth] | None
    items: tuple[ExtractedItem, ...]
    total_earnings: ExtractedField[Decimal] | None
    total_deductions: ExtractedField[Decimal] | None
    net: ExtractedField[Decimal] | None
    irrf_base: ExtractedField[Decimal] | None
    dependents: ExtractedField[int] | None
    layout_confidence: float
    layout_recognized: bool


@dataclass(frozen=True, slots=True)
class PayslipAnalysis:
    fields: PayslipAnalysisFields
    payslip: Payslip | None
    evidence: tuple[Evidence, ...]
    subscore: int
    rule_set_version: str
    sources: tuple[str, ...]
    not_validated: tuple[str, ...]
    layout_confidence: float


class _EvidenceBuilder:
    def __init__(self, rules: tuple[RuleDefinition, ...]) -> None:
        self._active = {rule.id: rule for rule in active_rules(rules)}
        self._triggered: dict[str, dict[str, str]] = {}
        self._not_verifiable: dict[str, dict[str, str]] = {}
        self._sources: dict[str, str] = {}

    def trigger(
        self,
        rule_id: str,
        details: dict[str, str] | None = None,
        *,
        source: str | None = None,
    ) -> None:
        if rule_id not in self._active:
            return
        target = self._triggered.setdefault(rule_id, {})
        if details is not None:
            target.update(details)
        if source is not None:
            self._sources[rule_id] = source

    def not_verifiable(
        self,
        rule_id: str,
        reason: str,
        *,
        source: str,
        details: dict[str, str] | None = None,
    ) -> None:
        if rule_id not in self._active or rule_id in self._triggered:
            return
        target = self._not_verifiable.setdefault(
            rule_id,
            {"rule": rule_id, "reason": reason},
        )
        if details is not None:
            target.update(details)
        self._sources.setdefault(rule_id, source)

    def triggered_ids(self) -> set[str]:
        return set(self._triggered)

    def build(self) -> tuple[Evidence, ...]:
        evidence: list[Evidence] = []
        for rule_id in sorted(self._active):
            rule = self._active[rule_id]
            source = self._sources.get(rule_id, rule.source or "")
            if rule_id in self._triggered:
                evidence.append(
                    Evidence(
                        rule_id=rule.id,
                        rule_version=rule.version,
                        severity=rule.severity,
                        weight=rule.weight,
                        message_key=rule.message_key,
                        source=source,
                        details=dict(self._triggered[rule_id]),
                        status=EvidenceStatus.TRIGGERED,
                    ),
                )
            elif rule_id in self._not_verifiable:
                evidence.append(
                    Evidence(
                        rule_id=rule.id,
                        rule_version=rule.version,
                        severity=Severity.INFO,
                        weight=0,
                        message_key="payslip.not_verifiable",
                        source=source,
                        details=dict(self._not_verifiable[rule_id]),
                        status=EvidenceStatus.NOT_VERIFIABLE,
                    ),
                )
        return tuple(evidence)


def _build_payslip(fields: PayslipFields) -> Payslip:
    employee_cpf = fields.employee_cpf.value if fields.employee_cpf is not None else None
    items = tuple(
        PayslipItem(
            description=item.description,
            kind=item.kind,
            category=item.category,
            amount=item.amount,
            overtime_percent=item.overtime_percent,
            confidence=item.confidence,
        )
        for item in fields.items
    )
    return Payslip(
        employer_name=fields.employer_name.value if fields.employer_name is not None else None,
        employer_cnpj=fields.employer_cnpj.value if fields.employer_cnpj is not None else None,
        employee_name=fields.employee_name.value if fields.employee_name is not None else None,
        employee_cpf_masked=employee_cpf.masked if employee_cpf is not None else None,
        employee_cpf_valid=employee_cpf.is_valid if employee_cpf is not None else None,
        competency=fields.competency.value if fields.competency is not None else None,
        items=items,
        total_earnings=(fields.total_earnings.value if fields.total_earnings is not None else None),
        total_deductions=(
            fields.total_deductions.value if fields.total_deductions is not None else None
        ),
        net=fields.net.value if fields.net is not None else None,
        irrf_base=fields.irrf_base.value if fields.irrf_base is not None else None,
        dependents=fields.dependents.value if fields.dependents is not None else None,
    )


def _analysis_fields(fields: PayslipFields) -> PayslipAnalysisFields:
    masked_cpf: ExtractedField[str] | None = None
    if fields.employee_cpf is not None:
        masked_cpf = ExtractedField(
            value=fields.employee_cpf.value.masked,
            confidence=fields.employee_cpf.confidence,
            raw=None,
        )
    return PayslipAnalysisFields(
        employer_name=fields.employer_name,
        employer_cnpj=fields.employer_cnpj,
        employee_name=fields.employee_name,
        employee_cpf_masked=masked_cpf,
        competency=fields.competency,
        items=fields.items,
        total_earnings=fields.total_earnings,
        total_deductions=fields.total_deductions,
        net=fields.net,
        irrf_base=fields.irrf_base,
        dependents=fields.dependents,
        layout_confidence=fields.layout_confidence,
        layout_recognized=fields.layout_recognized,
    )


def _sum_items(
    payslip: Payslip,
    category: ItemCategory,
    kind: ItemKind,
) -> Decimal:
    return sum(
        (item.amount for item in payslip.items if item.category is category and item.kind is kind),
        Decimal("0.00"),
    )


def _illegible_fields(fields: PayslipFields, payslip: Payslip) -> list[str]:
    illegible: list[str] = []
    checks: tuple[tuple[str, ExtractedField[object] | None], ...] = (
        ("employer_name", fields.employer_name),
        ("employer_cnpj", fields.employer_cnpj),
        ("employee_name", fields.employee_name),
        ("employee_cpf", fields.employee_cpf),
        ("competency", fields.competency),
        ("total_earnings", fields.total_earnings),
        ("total_deductions", fields.total_deductions),
        ("net", fields.net),
    )
    for name, field in checks:
        if field is None or field.confidence < 0.5:
            illegible.append(name)

    base_items = [
        item
        for item in payslip.items
        if item.category is ItemCategory.BASE_SALARY and item.kind is ItemKind.EARNING
    ]
    if not base_items or min(item.confidence for item in base_items) < 0.5:
        illegible.append("base_salary")

    inss_items = [
        item
        for item in payslip.items
        if item.category is ItemCategory.INSS and item.kind is ItemKind.DEDUCTION
    ]
    if not inss_items:
        illegible.append("inss")
    return illegible


def _check_totals(
    builder: _EvidenceBuilder,
    payslip: Payslip,
    *,
    has_unknown_items: bool,
) -> None:
    if has_unknown_items:
        for rule_id in (
            "earnings_total_mismatch",
            "deductions_total_mismatch",
            "net_mismatch",
        ):
            builder.not_verifiable(
                rule_id,
                "unknown_items",
                source="knowledge/fraud_patterns/holerite.pdf#1.2",
            )
        return

    if payslip.total_earnings is None:
        builder.not_verifiable(
            "earnings_total_mismatch",
            "missing_total_earnings",
            source="knowledge/fraud_patterns/holerite.pdf#1.2",
        )
    elif not payslip.earning_items:
        builder.not_verifiable(
            "earnings_total_mismatch",
            "no_earning_items",
            source="knowledge/fraud_patterns/holerite.pdf#1.2",
        )
    elif _money(payslip.total_earnings) != _money(payslip.earnings_sum):
        builder.trigger(
            "earnings_total_mismatch",
            {
                "declared": str(_money(payslip.total_earnings)),
                "computed": str(_money(payslip.earnings_sum)),
            },
        )

    if payslip.total_deductions is None:
        builder.not_verifiable(
            "deductions_total_mismatch",
            "missing_total_deductions",
            source="knowledge/fraud_patterns/holerite.pdf#1.2",
        )
    elif not payslip.deduction_items:
        builder.not_verifiable(
            "deductions_total_mismatch",
            "no_deduction_items",
            source="knowledge/fraud_patterns/holerite.pdf#1.2",
        )
    elif _money(payslip.total_deductions) != _money(payslip.deductions_sum):
        builder.trigger(
            "deductions_total_mismatch",
            {
                "declared": str(_money(payslip.total_deductions)),
                "computed": str(_money(payslip.deductions_sum)),
            },
        )

    if payslip.net is None or payslip.total_earnings is None or payslip.total_deductions is None:
        builder.not_verifiable(
            "net_mismatch",
            "missing_net_or_totals",
            source="knowledge/fraud_patterns/holerite.pdf#1.2",
        )
        return

    if payslip.net > payslip.total_earnings:
        builder.trigger(
            "net_exceeds_earnings",
            {
                "net": str(_money(payslip.net)),
                "earnings": str(_money(payslip.total_earnings)),
            },
        )
    else:
        expected = _money(payslip.total_earnings - payslip.total_deductions)
        if _money(payslip.net) != expected:
            builder.trigger(
                "net_mismatch",
                {
                    "declared": str(_money(payslip.net)),
                    "computed": str(expected),
                },
            )


def _check_rounding(builder: _EvidenceBuilder, payslip: Payslip) -> None:
    fields: list[str] = []
    for item in payslip.items:
        if item.amount != _money(item.amount):
            fields.append(f"item:{item.description}")
    for name, value in (
        ("total_earnings", payslip.total_earnings),
        ("total_deductions", payslip.total_deductions),
        ("net", payslip.net),
        ("irrf_base", payslip.irrf_base),
    ):
        if value is not None and value != _money(value):
            fields.append(name)
    if fields:
        builder.trigger("rounding_incoherent", {"fields": ",".join(sorted(fields))})


def _check_duplicates(builder: _EvidenceBuilder, payslip: Payslip) -> None:
    counts: dict[tuple[str, ItemKind, Decimal], int] = {}
    for item in payslip.items:
        key = (_normalize_description(item.description), item.kind, _money(item.amount))
        counts[key] = counts.get(key, 0) + 1
    duplicates = [
        (description, amount, count)
        for (description, _kind, amount), count in counts.items()
        if count > 1
    ]
    if duplicates:
        details = ";".join(
            f"{description}={amount}x{count}" for description, amount, count in sorted(duplicates)
        )
        builder.trigger("duplicate_item", {"items": details})


def _check_inss(
    builder: _EvidenceBuilder,
    payslip: Payslip,
    regulatory: RegulatoryTables,
    not_validated: list[str],
) -> None:
    if payslip.competency is None:
        builder.not_verifiable(
            "inss_mismatch",
            "missing_competency",
            source=regulatory.inss.source,
        )
        return
    table = regulatory.inss_for(payslip.competency)
    if table is None:
        not_validated.append("inss_table_missing")
        builder.not_verifiable(
            "inss_mismatch",
            "missing_inss_table",
            source=regulatory.inss.source,
            details={"competency": str(payslip.competency)},
        )
        return
    if payslip.total_earnings is None:
        builder.not_verifiable(
            "inss_mismatch",
            "missing_total_earnings",
            source=table.source,
        )
        return
    actual = _sum_items(payslip, ItemCategory.INSS, ItemKind.DEDUCTION)
    expected = table.calculate(payslip.total_earnings)
    if abs(actual - expected) > _TOLERANCE:
        builder.trigger(
            "inss_mismatch",
            {
                "competency": str(payslip.competency),
                "expected": str(expected),
                "actual": str(_money(actual)),
            },
            source=table.source,
        )


def _check_irrf(
    builder: _EvidenceBuilder,
    payslip: Payslip,
    regulatory: RegulatoryTables,
    not_validated: list[str],
) -> None:
    if payslip.competency is None:
        builder.not_verifiable(
            "irrf_mismatch",
            "missing_competency",
            source=regulatory.irrf.source,
        )
        return
    table = regulatory.irrf_for(payslip.competency)
    if table is None:
        not_validated.append("irrf_table_missing")
        builder.not_verifiable(
            "irrf_mismatch",
            "missing_irrf_table",
            source=regulatory.irrf.source,
            details={"competency": str(payslip.competency)},
        )
        return
    if payslip.irrf_base is None:
        not_validated.append("irrf_base_missing")
        builder.not_verifiable(
            "irrf_mismatch",
            "missing_irrf_base",
            source=table.source,
        )
        return
    actual = _sum_items(payslip, ItemCategory.IRRF, ItemKind.DEDUCTION)
    expected = table.calculate(payslip.irrf_base)
    if abs(actual - expected) > _TOLERANCE:
        builder.trigger(
            "irrf_mismatch",
            {
                "competency": str(payslip.competency),
                "expected": str(expected),
                "actual": str(_money(actual)),
            },
            source=table.source,
        )


def _check_minimum_wage(
    builder: _EvidenceBuilder,
    payslip: Payslip,
    regulatory: RegulatoryTables,
    not_validated: list[str],
) -> None:
    if payslip.competency is None:
        builder.not_verifiable(
            "base_below_minimum",
            "missing_competency",
            source=regulatory.minimum_wage.source,
        )
        return
    base_items = [
        item
        for item in payslip.items
        if item.category is ItemCategory.BASE_SALARY and item.kind is ItemKind.EARNING
    ]
    if not base_items:
        not_validated.append("base_salary_missing")
        builder.not_verifiable(
            "base_below_minimum",
            "missing_base_salary",
            source=regulatory.minimum_wage.source,
        )
        return
    wage = regulatory.minimum_wage.for_date(payslip.competency.first_day)
    if wage is None:
        not_validated.append("minimum_wage_table_missing")
        builder.not_verifiable(
            "base_below_minimum",
            "missing_minimum_wage_table",
            source=regulatory.minimum_wage.source,
            details={"competency": str(payslip.competency)},
        )
        return
    base = sum((item.amount for item in base_items), Decimal("0.00"))
    if base < wage.value:
        builder.trigger(
            "base_below_minimum",
            {
                "competency": str(payslip.competency),
                "minimum": str(_money(wage.value)),
                "actual": str(_money(base)),
            },
            source=wage.source,
        )


def _check_overtime(
    builder: _EvidenceBuilder,
    payslip: Payslip,
    regulatory: RegulatoryTables,
    not_validated: list[str],
) -> None:
    overtime_items = [
        item
        for item in payslip.items
        if item.category is ItemCategory.OVERTIME and item.kind is ItemKind.EARNING
    ]
    if not overtime_items:
        return
    if payslip.competency is None:
        builder.not_verifiable(
            "overtime_below_minimum",
            "missing_competency",
            source=regulatory.clt.source,
        )
        return
    parameter = regulatory.clt_parameter_for(
        _OVERTIME_PARAMETER,
        payslip.competency,
    )
    if parameter is None:
        not_validated.append("overtime_parameter_missing")
        builder.not_verifiable(
            "overtime_below_minimum",
            "missing_overtime_parameter",
            source=regulatory.clt.source,
            details={"competency": str(payslip.competency)},
        )
        return
    percents = [
        item.overtime_percent for item in overtime_items if item.overtime_percent is not None
    ]
    if not percents:
        not_validated.append("overtime_percent_missing")
        builder.not_verifiable(
            "overtime_below_minimum",
            "missing_overtime_percent",
            source=parameter.source,
        )
        return
    if any(percent < parameter.value for percent in percents):
        builder.trigger(
            "overtime_below_minimum",
            {
                "minimum": str(parameter.value),
                "actual": ",".join(str(percent) for percent in sorted(percents)),
            },
            source=parameter.source,
        )


def analyze_payslip(
    fields: PayslipFields,
    *,
    regulatory: RegulatoryTables | None = None,
    reference_date: date | None = None,
    rules: tuple[RuleDefinition, ...] = RULES,
) -> PayslipAnalysis:
    tables = regulatory if regulatory is not None else load_regulatory_tables()
    today = reference_date if reference_date is not None else date.today()
    builder = _EvidenceBuilder(rules)
    not_validated = [
        "receita_cnpj_registry",
        "cpf_registry",
        "esocial_registry",
        "official_rounding_policy",
        "cpf_cnpj_dv_source",
    ]
    if not fields.layout_recognized:
        not_validated.append("payslip_layout_unknown")

    payslip = _build_payslip(fields)
    illegible = _illegible_fields(fields, payslip)
    if illegible:
        builder.trigger("field_illegible", {"fields": ",".join(sorted(set(illegible)))})

    has_unknown_items = any(item.kind is ItemKind.UNKNOWN for item in payslip.items)
    _check_totals(builder, payslip, has_unknown_items=has_unknown_items)
    _check_rounding(builder, payslip)
    _check_duplicates(builder, payslip)

    if payslip.competency is not None and payslip.competency.first_day > today:
        builder.trigger(
            "competency_implausible",
            {
                "competency": str(payslip.competency),
                "reference_date": today.isoformat(),
            },
        )

    if payslip.employer_cnpj is not None and not payslip.employer_cnpj.is_valid:
        builder.trigger(
            "employer_cnpj_invalid",
            {"cnpj": _mask_cnpj(payslip.employer_cnpj.digits)},
        )
    if payslip.employee_cpf_valid is False:
        builder.trigger(
            "employee_cpf_invalid",
            {"cpf": payslip.employee_cpf_masked or ""},
        )

    _check_inss(builder, payslip, tables, not_validated)
    _check_irrf(builder, payslip, tables, not_validated)
    _check_minimum_wage(builder, payslip, tables, not_validated)
    _check_overtime(builder, payslip, tables, not_validated)

    evidence = builder.build()
    triggered = builder.triggered_ids()
    active = active_rules(rules)
    raw_score = sum(rule.weight for rule in active if rule.id in triggered)
    critical = any(rule.severity is Severity.CRITICAL for rule in active if rule.id in triggered)
    subscore = min(100, raw_score)
    if critical:
        subscore = max(subscore, CRITICAL_FLOOR)

    return PayslipAnalysis(
        fields=_analysis_fields(fields),
        payslip=payslip,
        evidence=evidence,
        subscore=subscore,
        rule_set_version=RULE_SET_VERSION,
        sources=tuple(sorted({item.source for item in evidence})),
        not_validated=tuple(dict.fromkeys(not_validated)),
        layout_confidence=fields.layout_confidence,
    )
