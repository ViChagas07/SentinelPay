import math

from paysentineliq.domain.boleto.analysis import BoletoAnalysis
from paysentineliq.domain.boleto.rules import RULES as BOLETO_RULES
from paysentineliq.domain.ingestion import VisualSignal
from paysentineliq.domain.payslip.analysis import PayslipAnalysis
from paysentineliq.domain.payslip.models import ItemKind
from paysentineliq.domain.payslip.rules import (
    RULES as PAYSLIP_RULES,
)
from paysentineliq.domain.payslip.rules import (
    EvidenceStatus,
)
from paysentineliq.domain.receipt.analysis import ReceiptAnalysis
from paysentineliq.domain.scoring import (
    DeterministicSummary,
    EvidenceSummary,
    SeverityLevel,
)

RULE_VOCABULARY = tuple(
    sorted({rule.id for rule in BOLETO_RULES} | {rule.id for rule in PAYSLIP_RULES}),
)

_BASE_FEATURES = (
    "subscore_norm",
    "evidence_count",
    "critical_count",
    "high_count",
    "medium_count",
    "low_count",
    "info_count",
    "weighted_sum_norm",
    "not_validated_count",
    "min_field_confidence",
    "mean_field_confidence",
    "low_confidence_count",
    "is_boleto",
    "is_payslip",
    "amount_log",
    "due_factor_norm",
    "barcode_read",
    "has_unknown_items",
    "item_count_norm",
    "deduction_earnings_ratio",
    "net_earnings_ratio",
    "visual_count",
    "visual_max",
    "visual_mean",
)

FEATURE_NAMES = _BASE_FEATURES + tuple(f"rule_{rule_id}" for rule_id in RULE_VOCABULARY)


def _barcode_feature(value: bool | None) -> float:
    if value is True:
        return 1.0
    if value is False:
        return 0.0
    return 0.5


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _visual_values(signals: tuple[VisualSignal, ...]) -> tuple[float, ...]:
    return tuple(_clamp(signal.value) for signal in signals)


def visual_score(signals: tuple[VisualSignal, ...]) -> float:
    values = _visual_values(signals)
    return max(values, default=0.0)


def _confidence(field: object | None) -> float | None:
    if field is None:
        return None
    confidence = getattr(field, "confidence", None)
    return float(confidence) if confidence is not None else None


def _field_confidences(fields: tuple[object | None, ...]) -> tuple[float, ...]:
    return tuple(confidence for field in fields if (confidence := _confidence(field)) is not None)


def summary_from_boleto(analysis: BoletoAnalysis) -> DeterministicSummary:
    fields = analysis.fields
    confidences = _field_confidences(
        (
            fields.line,
            fields.amount,
            fields.due_date,
            fields.beneficiary,
            fields.beneficiary_tax_id,
            fields.payer_tax_id,
            fields.bank_header,
        ),
    )
    decoded = analysis.decoded
    barcode_read: bool | None
    if analysis.barcode_read.status == "read":
        barcode_read = True
    elif analysis.barcode_read.status in ("not_found", "error"):
        barcode_read = False
    else:
        barcode_read = None
    return DeterministicSummary(
        document_type="boleto",
        subscore=analysis.subscore,
        evidence=tuple(
            EvidenceSummary(
                rule_id=evidence.rule_id,
                severity=SeverityLevel(evidence.severity.value),
                weight=evidence.weight,
            )
            for evidence in analysis.evidence
        ),
        field_confidences=confidences,
        not_validated_count=len(analysis.not_validated),
        amount_cents=decoded.amount.cents if decoded is not None else None,
        due_factor=decoded.due_factor if decoded is not None else None,
        barcode_read=barcode_read,
    )


def summary_from_receipt(analysis: ReceiptAnalysis) -> DeterministicSummary:
    fields = analysis.fields
    confidences = _field_confidences(
        (
            fields.line,
            fields.barcode,
            fields.amount,
            fields.due_date,
            fields.issuer,
            fields.reference,
        ),
    )
    amount = fields.amount
    amount_cents = None
    if amount is not None:
        scaled = amount.value * 100
        if scaled == scaled.to_integral_value():
            amount_cents = int(scaled)
    return DeterministicSummary(
        document_type="receipt",
        subscore=analysis.subscore,
        evidence=tuple(
            EvidenceSummary(
                rule_id=evidence.rule_id,
                severity=evidence.severity,
                weight=evidence.weight,
            )
            for evidence in analysis.evidence
        ),
        field_confidences=confidences,
        not_validated_count=len(analysis.not_validated),
        amount_cents=amount_cents,
        due_factor=None,
        barcode_read=True if analysis.barcode_checked else None,
    )


def summary_from_payslip(analysis: PayslipAnalysis) -> DeterministicSummary:
    fields = analysis.fields
    payslip = analysis.payslip
    item_confidences = (
        tuple(item.confidence for item in payslip.items) if payslip is not None else ()
    )
    confidences = (
        _field_confidences(
            (
                fields.employer_name,
                fields.employer_cnpj,
                fields.employee_name,
                fields.employee_cpf_masked,
                fields.competency,
                fields.total_earnings,
                fields.total_deductions,
                fields.net,
                fields.irrf_base,
                fields.dependents,
            ),
        )
        + item_confidences
    )
    return DeterministicSummary(
        document_type="payslip",
        subscore=analysis.subscore,
        evidence=tuple(
            EvidenceSummary(
                rule_id=evidence.rule_id,
                severity=SeverityLevel(evidence.severity.value),
                weight=evidence.weight,
            )
            for evidence in analysis.evidence
            if evidence.status is EvidenceStatus.TRIGGERED
        ),
        field_confidences=confidences,
        not_validated_count=len(analysis.not_validated),
        has_unknown_items=(
            any(item.kind is ItemKind.UNKNOWN for item in payslip.items)
            if payslip is not None
            else False
        ),
        item_count=len(payslip.items) if payslip is not None else 0,
        total_earnings=payslip.total_earnings if payslip is not None else None,
        total_deductions=payslip.total_deductions if payslip is not None else None,
        net=payslip.net if payslip is not None else None,
    )


def build_feature_vector(
    summary: DeterministicSummary,
    visual_signals: tuple[VisualSignal, ...],
) -> tuple[float, ...]:
    severity_counts = {
        severity: float(
            sum(1 for evidence in summary.evidence if evidence.severity is severity),
        )
        for severity in SeverityLevel
    }
    confidences = summary.field_confidences
    min_confidence = min(confidences, default=0.0)
    mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    low_confidence_count = float(
        sum(1 for value in confidences if value < 0.5),
    )
    visual_values = _visual_values(visual_signals)
    visual_count = float(len(visual_values))
    visual_max = max(visual_values, default=0.0)
    visual_mean = sum(visual_values) / len(visual_values) if visual_values else 0.0

    earnings = summary.total_earnings
    deductions = summary.total_deductions
    net = summary.net
    deduction_ratio = 0.0
    net_ratio = 0.0
    if earnings is not None and earnings > 0:
        if deductions is not None:
            deduction_ratio = min(max(float(deductions / earnings), 0.0), 5.0)
        if net is not None:
            net_ratio = min(max(float(net / earnings), -1.0), 2.0)

    triggered = {evidence.rule_id for evidence in summary.evidence}
    base = (
        summary.subscore / 100.0,
        float(len(summary.evidence)),
        severity_counts[SeverityLevel.CRITICAL],
        severity_counts[SeverityLevel.HIGH],
        severity_counts[SeverityLevel.MEDIUM],
        severity_counts[SeverityLevel.LOW],
        severity_counts[SeverityLevel.INFO],
        sum(evidence.weight for evidence in summary.evidence) / 100.0,
        float(summary.not_validated_count),
        min_confidence,
        mean_confidence,
        low_confidence_count,
        1.0 if summary.document_type == "boleto" else 0.0,
        1.0 if summary.document_type == "payslip" else 0.0,
        math.log1p(summary.amount_cents) if summary.amount_cents is not None else 0.0,
        summary.due_factor / 9999.0 if summary.due_factor is not None else 0.0,
        _barcode_feature(summary.barcode_read),
        1.0 if summary.has_unknown_items else 0.0,
        min(summary.item_count, 50) / 50.0,
        deduction_ratio,
        net_ratio,
        visual_count,
        visual_max,
        visual_mean,
    )
    rule_features = tuple(1.0 if rule_id in triggered else 0.0 for rule_id in RULE_VOCABULARY)
    return tuple(float(value) for value in (*base, *rule_features))
