from dataclasses import dataclass
from datetime import date
from typing import Literal, cast

from paysentineliq.domain.boleto.bank_directory import BankDirectory, load_bank_directory
from paysentineliq.domain.boleto.due_date import due_date_from_factor
from paysentineliq.domain.boleto.extraction import BoletoFields, ExtractedField
from paysentineliq.domain.boleto.lines import (
    BankDigitableLine,
    Barcode,
    UtilityDigitableLine,
)
from paysentineliq.domain.boleto.money import Money
from paysentineliq.domain.boleto.rules import (
    CRITICAL_FLOOR,
    RULE_SET_VERSION,
    RULES,
    RuleDefinition,
    Severity,
    active_rules,
)
from paysentineliq.domain.boleto.tax_id import TaxId

BarcodeStatus = Literal["read", "not_validated", "not_found", "error"]

_BASE_NOT_VALIDATED = (
    "bacen_bank_registry",
    "cip_title_registry",
    "receita_tax_id_registry",
    "due_date_cycle_reset",
    "cpf_cnpj_dv_source",
)


@dataclass(frozen=True, slots=True)
class BarcodeRead:
    status: BarcodeStatus
    digits: str | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class BoletoDecoded:
    bank_code: str
    bank_name: str | None
    currency: str
    due_factor: int
    due_date: date | None
    amount: Money
    free_field: str


@dataclass(frozen=True, slots=True)
class Evidence:
    rule_id: str
    rule_version: str
    severity: Severity
    weight: int
    message_key: str
    source: str
    details: dict[str, str]


@dataclass(frozen=True, slots=True)
class BoletoAnalysis:
    fields: BoletoFields
    decoded: BoletoDecoded | None
    evidence: tuple[Evidence, ...]
    subscore: int
    rule_set_version: str
    sources: tuple[str, ...]
    not_validated: tuple[str, ...]
    barcode_read: BarcodeRead


class _EvidenceBuilder:
    def __init__(self, rules: tuple[RuleDefinition, ...]) -> None:
        self._active = {rule.id: rule for rule in active_rules(rules)}
        self._details: dict[str, dict[str, str]] = {}

    def add(self, rule_id: str, details: dict[str, str] | None = None) -> None:
        if rule_id not in self._active:
            return
        target = self._details.setdefault(rule_id, {})
        if details is not None:
            target.update(details)

    def build(self) -> tuple[Evidence, ...]:
        evidence: list[Evidence] = []
        for rule_id in sorted(self._details):
            rule = self._active[rule_id]
            if rule.source is None:
                continue
            evidence.append(
                Evidence(
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


def _finish(
    *,
    fields: BoletoFields,
    decoded: BoletoDecoded | None,
    builder: _EvidenceBuilder,
    barcode_read: BarcodeRead,
    not_validated: list[str],
    rules: tuple[RuleDefinition, ...],
) -> BoletoAnalysis:
    evidence = builder.build()
    triggered = {item.rule_id for item in evidence}
    active = active_rules(rules)
    raw_score = sum(rule.weight for rule in active if rule.id in triggered)
    critical = any(rule.severity is Severity.CRITICAL for rule in active if rule.id in triggered)
    subscore = min(100, raw_score)
    if critical:
        subscore = max(subscore, CRITICAL_FLOOR)
    return BoletoAnalysis(
        fields=fields,
        decoded=decoded,
        evidence=evidence,
        subscore=subscore,
        rule_set_version=RULE_SET_VERSION,
        sources=tuple(sorted({item.source for item in evidence})),
        not_validated=tuple(dict.fromkeys(not_validated)),
        barcode_read=barcode_read,
    )


def analyze_boleto(
    fields: BoletoFields,
    *,
    barcode_read: BarcodeRead | None = None,
    bank_directory: BankDirectory | None = None,
    rules: tuple[RuleDefinition, ...] = RULES,
) -> BoletoAnalysis:
    directory = bank_directory if bank_directory is not None else load_bank_directory()
    read = (
        barcode_read
        if barcode_read is not None
        else BarcodeRead(status="not_validated", reason="image_not_provided")
    )
    builder = _EvidenceBuilder(rules)
    not_validated = list(_BASE_NOT_VALIDATED)
    if read.status == "not_validated":
        not_validated.append("barcode_image_read")

    line: BankDigitableLine | None = None
    if fields.line is None:
        builder.add("line_invalid", {"reason": "missing"})
    elif len(fields.line.value) == 48:
        try:
            UtilityDigitableLine(fields.line.value)
        except ValueError:
            builder.add("line_invalid", {"reason": "non_numeric"})
        else:
            builder.add("utility_line_not_verifiable", {"length": "48"})
            not_validated.append("utility_line_layout")
            return _finish(
                fields=fields,
                decoded=None,
                builder=builder,
                barcode_read=read,
                not_validated=not_validated,
                rules=rules,
            )
    elif len(fields.line.value) == 47:
        try:
            line = BankDigitableLine(fields.line.value)
        except ValueError:
            builder.add("line_invalid", {"reason": "non_numeric"})
    else:
        builder.add(
            "line_invalid",
            {"reason": "length", "length": str(len(fields.line.value))},
        )

    barcode: Barcode | None = None
    if read.status == "read":
        if read.digits is None:
            builder.add("barcode_unreadable", {"reason": "missing_digits"})
            not_validated.append("barcode_image_read")
        else:
            try:
                barcode = Barcode(read.digits)
            except ValueError:
                builder.add("barcode_unreadable", {"reason": "invalid_digits"})
                not_validated.append("barcode_image_read")
    elif read.status in ("not_found", "error"):
        builder.add("barcode_unreadable", {"reason": read.reason or read.status})
        not_validated.append("barcode_image_read")

    if barcode is None and fields.barcode is not None:
        if fields.barcode.confidence >= 0.8:
            try:
                barcode = Barcode(fields.barcode.value)
            except ValueError:
                builder.add("barcode_unreadable", {"reason": "text_invalid"})
                not_validated.append("barcode_text_read")
        else:
            not_validated.append("barcode_text_low_confidence")

    if line is None and barcode is None:
        return _finish(
            fields=fields,
            decoded=None,
            builder=builder,
            barcode_read=read,
            not_validated=not_validated,
            rules=rules,
        )

    if line is not None:
        bank_code = line.bank_code
        currency = line.currency
        due_factor = line.due_factor
        amount_cents = line.amount_cents
        free_field = line.free_field
    else:
        barcode_value = cast(Barcode, barcode)
        bank_code = barcode_value.bank_code
        currency = barcode_value.currency
        due_factor = barcode_value.due_factor
        amount_cents = barcode_value.amount_cents
        free_field = barcode_value.free_field

    bank = directory.find_by_code(bank_code)
    decoded = BoletoDecoded(
        bank_code=bank_code,
        bank_name=bank.name if bank is not None else None,
        currency=currency,
        due_factor=due_factor,
        due_date=due_date_from_factor(due_factor),
        amount=Money(amount_cents),
        free_field=free_field,
    )

    failed_dv_fields: set[str] = set()
    if line is not None:
        failed_dv_fields.update(error.field for error in line.dv_errors(directory))
    if barcode is not None:
        for error in barcode.dv_errors(directory):
            failed_dv_fields.add("barcode_general" if line is not None else error.field)
    if failed_dv_fields:
        builder.add("dv_invalid", {"fields": ",".join(sorted(failed_dv_fields))})

    if line is not None and barcode is not None and line.to_barcode().digits != barcode.digits:
        builder.add("line_barcode_mismatch", {"reason": "digits_differ"})

    illegible: list[str] = []
    if fields.beneficiary is None or fields.beneficiary.confidence < 0.5:
        illegible.append("beneficiary")
    if fields.beneficiary_tax_id is None or fields.beneficiary_tax_id.confidence < 0.5:
        illegible.append("beneficiary_tax_id")

    if fields.amount is None:
        illegible.append("amount")
    else:
        if fields.amount.confidence < 0.5:
            illegible.append("amount")
        if fields.amount.value != decoded.amount.as_decimal:
            builder.add(
                "amount_mismatch",
                {
                    "text": format(fields.amount.value, "f"),
                    "decoded": format(decoded.amount.as_decimal, "f"),
                },
            )

    if fields.due_date is None:
        if decoded.due_date is not None:
            if fields.due_date_absent:
                builder.add(
                    "due_date_mismatch",
                    {"text": "absent", "decoded": decoded.due_date.isoformat()},
                )
            else:
                illegible.append("due_date")
    else:
        if fields.due_date.confidence < 0.5:
            illegible.append("due_date")
        if fields.due_date.value != decoded.due_date:
            builder.add(
                "due_date_mismatch",
                {
                    "text": fields.due_date.value.isoformat(),
                    "decoded": decoded.due_date.isoformat()
                    if decoded.due_date is not None
                    else "none",
                },
            )

    if fields.bank_header is None:
        illegible.append("bank_header")
    else:
        if fields.bank_header.confidence < 0.5:
            illegible.append("bank_header")
        if fields.bank_header.value.code != decoded.bank_code:
            builder.add(
                "bank_header_mismatch",
                {
                    "header": fields.bank_header.value.code,
                    "decoded": decoded.bank_code,
                },
            )

    if bank is None:
        builder.add(
            "bank_code_unknown",
            {"bank_code": decoded.bank_code, "bacen_confirmation": "not_validated"},
        )
    if decoded.currency != "9":
        builder.add("currency_unsupported", {"currency": decoded.currency})

    invalid_roles: list[str] = []
    masked: list[str] = []
    tax_ids: tuple[tuple[str, ExtractedField[TaxId] | None], ...] = (
        ("beneficiary", fields.beneficiary_tax_id),
        ("payer", fields.payer_tax_id),
    )
    for role, field in tax_ids:
        if field is None:
            continue
        if field.confidence < 0.5:
            illegible.append(f"{role}_tax_id")
        if not field.value.is_valid:
            invalid_roles.append(role)
            masked.append(field.value.masked)
    for index, field in enumerate(fields.additional_tax_ids, start=1):
        if not field.value.is_valid:
            invalid_roles.append(f"additional_{index}")
            masked.append(field.value.masked)
    if invalid_roles:
        builder.add(
            "tax_id_invalid",
            {"roles": ",".join(invalid_roles), "masked": ",".join(masked)},
        )

    if illegible:
        builder.add("field_illegible", {"fields": ",".join(sorted(set(illegible)))})

    return _finish(
        fields=fields,
        decoded=decoded,
        builder=builder,
        barcode_read=read,
        not_validated=not_validated,
        rules=rules,
    )
