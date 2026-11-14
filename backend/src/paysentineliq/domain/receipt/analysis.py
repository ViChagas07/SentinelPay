import re
from dataclasses import dataclass
from datetime import date

from paysentineliq.domain.boleto.digits import mod10, mod11
from paysentineliq.domain.boleto.lines import UtilityDigitableLine
from paysentineliq.domain.receipt.extraction import ReceiptFields
from paysentineliq.domain.receipt.rules import (
    CRITICAL_FLOOR,
    RULE_SET_VERSION,
    RULES,
    ReceiptRule,
    active_rules,
)
from paysentineliq.domain.scoring import SeverityLevel

_REFERENCE_MONTH_RE = re.compile(r"\b(\d{1,2})[/-](\d{4})\b")
_REFERENCE_YEAR_RE = re.compile(r"\b(\d{4})-(\d{1,2})\b")


@dataclass(frozen=True, slots=True)
class ReceiptDecoded:
    line: UtilityDigitableLine
    blocks: tuple[str, ...]
    dvs: tuple[int, ...]
    barcode_digits: str


@dataclass(frozen=True, slots=True)
class ReceiptEvidence:
    rule_id: str
    rule_version: str
    severity: SeverityLevel
    weight: int
    message_key: str
    source: str
    details: dict[str, str]


@dataclass(frozen=True, slots=True)
class ReceiptAnalysis:
    fields: ReceiptFields
    decoded: ReceiptDecoded | None
    evidence: tuple[ReceiptEvidence, ...]
    subscore: int
    rule_set_version: str
    sources: tuple[str, ...]
    not_validated: tuple[str, ...]
    barcode_checked: bool


class _Builder:
    def __init__(self, rules: tuple[ReceiptRule, ...]) -> None:
        self._active = {rule.id: rule for rule in active_rules(rules)}
        self._details: dict[str, dict[str, str]] = {}

    def add(self, rule_id: str, details: dict[str, str] | None = None) -> None:
        if rule_id not in self._active:
            return
        target = self._details.setdefault(rule_id, {})
        if details is not None:
            target.update(details)

    def build(self) -> tuple[ReceiptEvidence, ...]:
        evidence: list[ReceiptEvidence] = []
        for rule_id in sorted(self._details):
            rule = self._active[rule_id]
            if rule.source is None:
                continue
            evidence.append(
                ReceiptEvidence(
                    rule_id=rule.id,
                    rule_version=rule.version,
                    severity=rule.severity,
                    weight=rule.weight,
                    message_key=rule.message_key,
                    source=rule.source,
                    details=dict(self._details[rule_id]),
                ),
            )
        return tuple(evidence)


def _parse_reference(value: str) -> date | None:
    match = _REFERENCE_MONTH_RE.search(value)
    if match is not None:
        month, year = int(match.group(1)), int(match.group(2))
    else:
        match = _REFERENCE_YEAR_RE.search(value)
        if match is None:
            return None
        year, month = int(match.group(1)), int(match.group(2))
    try:
        return date(year, month, 1)
    except ValueError:
        return None


def _distinct_values(values: tuple[object, ...], confidence: tuple[float, ...]) -> int:
    selected = {value for value, conf in zip(values, confidence, strict=False) if conf >= 0.8}
    return len(selected)


def analyze_receipt(
    fields: ReceiptFields,
    *,
    rules: tuple[ReceiptRule, ...] = RULES,
) -> ReceiptAnalysis:
    builder = _Builder(rules)
    not_validated: list[str] = ["issuer_registry", "dv_algorithm"]
    decoded: ReceiptDecoded | None = None
    barcode_checked = False

    if fields.line is None:
        builder.add("receipt_line_invalid", {"reason": "missing"})
    else:
        try:
            line = UtilityDigitableLine(fields.line.value)
        except ValueError:
            builder.add("receipt_line_invalid", {"reason": "not_48_digits"})
        else:
            blocks = line.blocks()
            dvs = line.field_dvs()
            decoded = ReceiptDecoded(
                line=line,
                blocks=blocks,
                dvs=dvs,
                barcode_digits=line.barcode_digits(),
            )
            invalid_dvs: list[str] = []
            for index, (block, dv) in enumerate(zip(blocks, dvs, strict=True), start=1):
                if dv not in (mod10(block), mod11(block)):
                    invalid_dvs.append(str(index))
            if invalid_dvs:
                builder.add("receipt_dv_invalid", {"blocks": ",".join(invalid_dvs)})
            if fields.barcode is not None and fields.barcode.confidence >= 0.8:
                if len(fields.barcode.value) == 44:
                    barcode_checked = True
                    if fields.barcode.value != line.barcode_digits():
                        builder.add(
                            "receipt_barcode_mismatch",
                            {"reason": "digits_differ"},
                        )
                else:
                    builder.add("receipt_barcode_invalid", {"reason": "not_44_digits"})
            else:
                not_validated.append("barcode_text_read")

    amount = fields.amount
    if amount is None or amount.confidence < 0.5:
        builder.add("receipt_amount_missing", {"reason": "missing_or_low_confidence"})
    elif amount.value <= 0:
        builder.add("receipt_amount_missing", {"reason": "non_positive"})
    else:
        if (
            _distinct_values(
                tuple(item.value for item in fields.amount_candidates),
                tuple(item.confidence for item in fields.amount_candidates),
            )
            > 1
        ):
            builder.add("receipt_amount_inconsistent", {"reason": "multiple_values"})

    due_date = fields.due_date
    if due_date is None or due_date.confidence < 0.5:
        builder.add("receipt_due_date_missing", {"reason": "missing_or_low_confidence"})
    else:
        if (
            _distinct_values(
                tuple(item.value for item in fields.due_date_candidates),
                tuple(item.confidence for item in fields.due_date_candidates),
            )
            > 1
        ):
            builder.add("receipt_due_date_inconsistent", {"reason": "multiple_values"})
        if fields.reference is not None:
            reference_month = _parse_reference(fields.reference.value)
            if reference_month is not None and due_date.value < reference_month:
                builder.add(
                    "receipt_due_date_inconsistent",
                    {"reason": "before_reference"},
                )

    if fields.issuer is None or fields.issuer.confidence < 0.5:
        builder.add("receipt_issuer_missing", {"reason": "missing_or_low_confidence"})
    if fields.reference is None:
        builder.add("receipt_reference_missing", {"reason": "missing"})

    illegible: list[str] = []
    for name, field in (
        ("line", fields.line),
        ("amount", fields.amount),
        ("due_date", fields.due_date),
        ("issuer", fields.issuer),
    ):
        if field is not None and field.confidence < 0.5:
            illegible.append(name)
    if illegible:
        builder.add("receipt_field_illegible", {"fields": ",".join(illegible)})

    evidence = builder.build()
    triggered = {item.rule_id for item in evidence}
    active = active_rules(rules)
    raw_score = sum(rule.weight for rule in active if rule.id in triggered)
    critical = any(
        rule.severity is SeverityLevel.CRITICAL for rule in active if rule.id in triggered
    )
    subscore = min(100, raw_score)
    if critical:
        subscore = max(subscore, CRITICAL_FLOOR)
    return ReceiptAnalysis(
        fields=fields,
        decoded=decoded,
        evidence=evidence,
        subscore=subscore,
        rule_set_version=RULE_SET_VERSION,
        sources=tuple(sorted({item.source for item in evidence})),
        not_validated=tuple(dict.fromkeys(not_validated)),
        barcode_checked=barcode_checked,
    )
