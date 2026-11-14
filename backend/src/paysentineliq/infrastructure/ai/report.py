from typing import Any

from paysentineliq.domain.analysis import AnalysisEvidence
from paysentineliq.domain.boleto.analysis import BoletoAnalysis
from paysentineliq.domain.payslip.analysis import PayslipAnalysis
from paysentineliq.domain.receipt.analysis import ReceiptAnalysis


def _extracted(field: Any) -> dict[str, Any] | None:
    if field is None:
        return None
    return {"value": field.value, "confidence": field.confidence}


def _tax_id(field: Any) -> dict[str, Any] | None:
    if field is None:
        return None
    tax_id = field.value
    return {
        "masked": tax_id.masked,
        "valid": tax_id.is_valid,
        "confidence": field.confidence,
    }


def _bank_header(field: Any) -> dict[str, Any] | None:
    if field is None:
        return None
    return {
        "code": field.value.code,
        "name": field.value.name,
        "confidence": field.confidence,
    }


def boleto_fields(analysis: BoletoAnalysis) -> dict[str, Any]:
    fields = analysis.fields
    decoded = analysis.decoded
    return {
        "line": _extracted(fields.line),
        "barcode": _extracted(fields.barcode),
        "amount": _extracted(fields.amount),
        "due_date": _extracted(fields.due_date),
        "beneficiary": _extracted(fields.beneficiary),
        "beneficiary_tax_id": _tax_id(fields.beneficiary_tax_id),
        "payer": _extracted(fields.payer),
        "payer_tax_id": _tax_id(fields.payer_tax_id),
        "additional_tax_ids": [_tax_id(field) for field in fields.additional_tax_ids],
        "bank_header": _bank_header(fields.bank_header),
        "decoded": (
            {
                "bank_code": decoded.bank_code,
                "bank_name": decoded.bank_name,
                "currency": decoded.currency,
                "due_factor": decoded.due_factor,
                "due_date": decoded.due_date,
                "amount": decoded.amount.as_decimal,
                "free_field": decoded.free_field,
            }
            if decoded is not None
            else None
        ),
    }


def payslip_fields(analysis: PayslipAnalysis) -> dict[str, Any]:
    payslip = analysis.payslip
    if payslip is None:
        return {}
    return {
        "employer_name": payslip.employer_name,
        "employer_cnpj": (
            {
                "digits": payslip.employer_cnpj.digits,
                "masked": payslip.employer_cnpj.masked,
                "valid": payslip.employer_cnpj.is_valid,
            }
            if payslip.employer_cnpj is not None
            else None
        ),
        "employee_name": payslip.employee_name,
        "employee_cpf_masked": payslip.employee_cpf_masked,
        "employee_cpf_valid": payslip.employee_cpf_valid,
        "competency": str(payslip.competency) if payslip.competency else None,
        "items": [
            {
                "description": item.description,
                "kind": item.kind.value,
                "category": item.category.value,
                "amount": item.amount,
                "overtime_percent": item.overtime_percent,
                "confidence": item.confidence,
            }
            for item in payslip.items
        ],
        "total_earnings": payslip.total_earnings,
        "total_deductions": payslip.total_deductions,
        "net": payslip.net,
        "irrf_base": payslip.irrf_base,
        "dependents": payslip.dependents,
        "layout_confidence": analysis.layout_confidence,
    }


def boleto_evidence(analysis: BoletoAnalysis) -> tuple[AnalysisEvidence, ...]:
    return tuple(
        AnalysisEvidence(
            rule_id=item.rule_id,
            severity=item.severity.value,
            weight=item.weight,
            message_key=item.message_key,
            source=item.source,
        )
        for item in analysis.evidence
    )


def payslip_evidence(analysis: PayslipAnalysis) -> tuple[AnalysisEvidence, ...]:
    return tuple(
        AnalysisEvidence(
            rule_id=item.rule_id,
            severity=item.severity.value,
            weight=item.weight,
            message_key=item.message_key,
            source=item.source,
        )
        for item in analysis.evidence
    )


def receipt_fields(analysis: ReceiptAnalysis) -> dict[str, Any]:
    fields = analysis.fields
    decoded = analysis.decoded
    return {
        "line": _extracted(fields.line),
        "barcode": _extracted(fields.barcode),
        "amount": (
            {"value": str(fields.amount.value), "confidence": fields.amount.confidence}
            if fields.amount is not None
            else None
        ),
        "due_date": (
            {
                "value": fields.due_date.value.isoformat(),
                "confidence": fields.due_date.confidence,
            }
            if fields.due_date is not None
            else None
        ),
        "issuer": _extracted(fields.issuer),
        "reference": _extracted(fields.reference),
        "decoded": (
            {
                "blocks": list(decoded.blocks),
                "dvs": list(decoded.dvs),
                "barcode": decoded.barcode_digits,
            }
            if decoded is not None
            else None
        ),
        "barcode_checked": analysis.barcode_checked,
        "not_validated": list(analysis.not_validated),
    }


def receipt_evidence(analysis: ReceiptAnalysis) -> tuple[AnalysisEvidence, ...]:
    return tuple(
        AnalysisEvidence(
            rule_id=item.rule_id,
            severity=item.severity.value,
            weight=item.weight,
            message_key=item.message_key,
            source=item.source,
        )
        for item in analysis.evidence
    )
