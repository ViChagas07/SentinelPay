from dataclasses import dataclass
from enum import StrEnum

from paysentineliq.domain.boleto.sources import (
    LAYOUT_BRADESCO,
    MANUAL_FEBRABAN,
)


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


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


RULE_SET_VERSION = "febraban-v1"
CRITICAL_FLOOR = 80

RULES: tuple[RuleDefinition, ...] = (
    RuleDefinition(
        id="line_invalid",
        version="1",
        severity=Severity.CRITICAL,
        weight=60,
        source=f"{MANUAL_FEBRABAN}#1.2",
        message_key="boleto.line_invalid",
    ),
    RuleDefinition(
        id="dv_invalid",
        version="1",
        severity=Severity.CRITICAL,
        weight=70,
        source=f"{MANUAL_FEBRABAN}#1.5; {LAYOUT_BRADESCO}#2",
        message_key="boleto.dv_invalid",
    ),
    RuleDefinition(
        id="line_barcode_mismatch",
        version="1",
        severity=Severity.CRITICAL,
        weight=70,
        source=f"{MANUAL_FEBRABAN}#1.2-1.3",
        message_key="boleto.line_barcode_mismatch",
    ),
    RuleDefinition(
        id="amount_mismatch",
        version="1",
        severity=Severity.CRITICAL,
        weight=70,
        source=f"{MANUAL_FEBRABAN}#1.3-1.4",
        message_key="boleto.amount_mismatch",
    ),
    RuleDefinition(
        id="due_date_mismatch",
        version="1",
        severity=Severity.HIGH,
        weight=30,
        source=f"{MANUAL_FEBRABAN}#1.4",
        message_key="boleto.due_date_mismatch",
    ),
    RuleDefinition(
        id="bank_header_mismatch",
        version="1",
        severity=Severity.HIGH,
        weight=30,
        source=f"{MANUAL_FEBRABAN}#1.6",
        message_key="boleto.bank_header_mismatch",
    ),
    RuleDefinition(
        id="bank_code_unknown",
        version="1",
        severity=Severity.HIGH,
        weight=20,
        source=f"{MANUAL_FEBRABAN}#1.6",
        message_key="boleto.bank_code_unknown",
    ),
    RuleDefinition(
        id="currency_unsupported",
        version="1",
        severity=Severity.HIGH,
        weight=15,
        source=f"{MANUAL_FEBRABAN}#1.2-1.3",
        message_key="boleto.currency_unsupported",
    ),
    RuleDefinition(
        id="tax_id_invalid",
        version="1",
        severity=Severity.HIGH,
        weight=25,
        source=f"{MANUAL_FEBRABAN}#3",
        message_key="boleto.tax_id_invalid",
    ),
    RuleDefinition(
        id="field_illegible",
        version="1",
        severity=Severity.MEDIUM,
        weight=10,
        source=f"{MANUAL_FEBRABAN}#1.1",
        message_key="boleto.field_illegible",
    ),
    RuleDefinition(
        id="barcode_unreadable",
        version="1",
        severity=Severity.MEDIUM,
        weight=10,
        source=f"{MANUAL_FEBRABAN}#1.1",
        message_key="boleto.barcode_unreadable",
    ),
    RuleDefinition(
        id="utility_line_not_verifiable",
        version="1",
        severity=Severity.INFO,
        weight=0,
        source=f"{MANUAL_FEBRABAN}#1.2",
        message_key="boleto.utility_line_not_verifiable",
    ),
)


def _is_registered_source(source: str) -> bool:
    return source.startswith("knowledge/febraban/") or source.startswith("knowledge/layouts/")


def active_rules(
    rules: tuple[RuleDefinition, ...] = RULES,
) -> tuple[RuleDefinition, ...]:
    return tuple(
        rule for rule in rules if rule.source is not None and _is_registered_source(rule.source)
    )
