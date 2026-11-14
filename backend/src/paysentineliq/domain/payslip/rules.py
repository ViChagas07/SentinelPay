from dataclasses import dataclass
from enum import StrEnum

HOLERITE = "knowledge/fraud_patterns/holerite.pdf"
FOLHA = "knowledge/fraud_patterns/folha_pagamento.pdf"
INSS_DATA = "data/regulatory/inss.yaml"
IRRF_DATA = "data/regulatory/irrf.yaml"
MINIMUM_WAGE_DATA = "data/regulatory/salario_minimo.yaml"
CLT_DATA = "data/regulatory/clt.yaml"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class EvidenceStatus(StrEnum):
    TRIGGERED = "triggered"
    NOT_VERIFIABLE = "not_verifiable"


@dataclass(frozen=True, slots=True)
class RuleDefinition:
    id: str
    version: str
    severity: Severity
    weight: int
    source: str | None
    message_key: str

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("rule id is required")
        if not self.version.strip():
            raise ValueError("rule version is required")
        if self.weight < 0:
            raise ValueError("rule weight must be non-negative")
        if not self.message_key.strip():
            raise ValueError("rule message key is required")


@dataclass(frozen=True, slots=True)
class Evidence:
    rule_id: str
    rule_version: str
    severity: Severity
    weight: int
    message_key: str
    source: str
    details: dict[str, str]
    status: EvidenceStatus


RULE_SET_VERSION = "payslip-v1"
CRITICAL_FLOOR = 80

RULES: tuple[RuleDefinition, ...] = (
    RuleDefinition(
        id="earnings_total_mismatch",
        version="1",
        severity=Severity.HIGH,
        weight=25,
        source=f"{HOLERITE}#1.2",
        message_key="payslip.earnings_total_mismatch",
    ),
    RuleDefinition(
        id="deductions_total_mismatch",
        version="1",
        severity=Severity.HIGH,
        weight=25,
        source=f"{HOLERITE}#1.2",
        message_key="payslip.deductions_total_mismatch",
    ),
    RuleDefinition(
        id="net_mismatch",
        version="1",
        severity=Severity.HIGH,
        weight=30,
        source=f"{HOLERITE}#1.2",
        message_key="payslip.net_mismatch",
    ),
    RuleDefinition(
        id="net_exceeds_earnings",
        version="1",
        severity=Severity.CRITICAL,
        weight=70,
        source=f"{FOLHA}#1.1",
        message_key="payslip.net_exceeds_earnings",
    ),
    RuleDefinition(
        id="inss_mismatch",
        version="1",
        severity=Severity.HIGH,
        weight=30,
        source=INSS_DATA,
        message_key="payslip.inss_mismatch",
    ),
    RuleDefinition(
        id="irrf_mismatch",
        version="1",
        severity=Severity.HIGH,
        weight=30,
        source=IRRF_DATA,
        message_key="payslip.irrf_mismatch",
    ),
    RuleDefinition(
        id="base_below_minimum",
        version="1",
        severity=Severity.HIGH,
        weight=30,
        source=MINIMUM_WAGE_DATA,
        message_key="payslip.base_below_minimum",
    ),
    RuleDefinition(
        id="overtime_below_minimum",
        version="1",
        severity=Severity.HIGH,
        weight=20,
        source=CLT_DATA,
        message_key="payslip.overtime_below_minimum",
    ),
    RuleDefinition(
        id="competency_implausible",
        version="1",
        severity=Severity.MEDIUM,
        weight=10,
        source=f"{HOLERITE}#1",
        message_key="payslip.competency_implausible",
    ),
    RuleDefinition(
        id="employer_cnpj_invalid",
        version="1",
        severity=Severity.HIGH,
        weight=25,
        source=f"{HOLERITE}#1; {FOLHA}#1.1",
        message_key="payslip.employer_cnpj_invalid",
    ),
    RuleDefinition(
        id="employee_cpf_invalid",
        version="1",
        severity=Severity.HIGH,
        weight=25,
        source=f"{HOLERITE}#1; {FOLHA}#1.1",
        message_key="payslip.employee_cpf_invalid",
    ),
    RuleDefinition(
        id="duplicate_item",
        version="1",
        severity=Severity.HIGH,
        weight=25,
        source=f"{HOLERITE}#1; {FOLHA}#1.1",
        message_key="payslip.duplicate_item",
    ),
    RuleDefinition(
        id="rounding_incoherent",
        version="1",
        severity=Severity.LOW,
        weight=5,
        source=f"{HOLERITE}#1.2; {FOLHA}#1.1",
        message_key="payslip.rounding_incoherent",
    ),
    RuleDefinition(
        id="field_illegible",
        version="1",
        severity=Severity.MEDIUM,
        weight=10,
        source=f"{HOLERITE}#1",
        message_key="payslip.field_illegible",
    ),
)


def _is_registered_source(source: str) -> bool:
    return source.startswith(
        ("knowledge/fraud_patterns/", "data/regulatory/"),
    )


def active_rules(
    rules: tuple[RuleDefinition, ...] = RULES,
) -> tuple[RuleDefinition, ...]:
    return tuple(
        rule for rule in rules if rule.source is not None and _is_registered_source(rule.source)
    )
