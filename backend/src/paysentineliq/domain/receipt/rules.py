from dataclasses import dataclass

from paysentineliq.domain.boleto.sources import MANUAL_FEBRABAN
from paysentineliq.domain.scoring import SeverityLevel

FAQ = "knowledge/faq/antifraud_faq.pdf"
RULE_SET_VERSION = "receipt-v1"
CRITICAL_FLOOR = 80


@dataclass(frozen=True, slots=True)
class ReceiptRule:
    id: str
    version: str
    severity: SeverityLevel
    weight: int
    source: str | None
    message_key: str


RULES: tuple[ReceiptRule, ...] = (
    ReceiptRule(
        "receipt_line_invalid",
        "1",
        SeverityLevel.CRITICAL,
        60,
        f"{MANUAL_FEBRABAN}#1.2; {FAQ}#P04",
        "receipt.line_invalid",
    ),
    ReceiptRule(
        "receipt_dv_invalid",
        "1",
        SeverityLevel.CRITICAL,
        70,
        f"{MANUAL_FEBRABAN}#1.5",
        "receipt.dv_invalid",
    ),
    ReceiptRule(
        "receipt_barcode_mismatch",
        "1",
        SeverityLevel.CRITICAL,
        70,
        f"{MANUAL_FEBRABAN}#1.2-1.3; {FAQ}#P06",
        "receipt.barcode_mismatch",
    ),
    ReceiptRule(
        "receipt_barcode_invalid",
        "1",
        SeverityLevel.MEDIUM,
        10,
        f"{MANUAL_FEBRABAN}#1.1",
        "receipt.barcode_invalid",
    ),
    ReceiptRule(
        "receipt_amount_inconsistent",
        "1",
        SeverityLevel.CRITICAL,
        70,
        f"{MANUAL_FEBRABAN}#1.3-1.4",
        "receipt.amount_inconsistent",
    ),
    ReceiptRule(
        "receipt_due_date_inconsistent",
        "1",
        SeverityLevel.HIGH,
        30,
        f"{MANUAL_FEBRABAN}#1.4",
        "receipt.due_date_inconsistent",
    ),
    ReceiptRule(
        "receipt_amount_missing",
        "1",
        SeverityLevel.HIGH,
        25,
        f"{MANUAL_FEBRABAN}#1.3",
        "receipt.amount_missing",
    ),
    ReceiptRule(
        "receipt_due_date_missing",
        "1",
        SeverityLevel.HIGH,
        25,
        f"{MANUAL_FEBRABAN}#1.4",
        "receipt.due_date_missing",
    ),
    ReceiptRule(
        "receipt_issuer_missing",
        "1",
        SeverityLevel.MEDIUM,
        10,
        f"{FAQ}#P04",
        "receipt.issuer_missing",
    ),
    ReceiptRule(
        "receipt_reference_missing",
        "1",
        SeverityLevel.LOW,
        5,
        f"{MANUAL_FEBRABAN}#1.1",
        "receipt.reference_missing",
    ),
    ReceiptRule(
        "receipt_field_illegible",
        "1",
        SeverityLevel.MEDIUM,
        10,
        f"{MANUAL_FEBRABAN}#1.1",
        "receipt.field_illegible",
    ),
)


def _is_registered_source(source: str) -> bool:
    return source.startswith("knowledge/febraban/") or source.startswith("knowledge/faq/")


def active_rules(rules: tuple[ReceiptRule, ...] = RULES) -> tuple[ReceiptRule, ...]:
    return tuple(
        rule for rule in rules if rule.source is not None and _is_registered_source(rule.source)
    )
