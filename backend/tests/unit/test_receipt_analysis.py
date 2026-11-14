from datetime import date
from decimal import Decimal

import pytest

from paysentineliq.application.queries.fraud_features import summary_from_receipt
from paysentineliq.application.queries.fraud_scoring import (
    FraudScoringRequest,
    FraudScoringService,
)
from paysentineliq.domain.boleto.lines import UtilityDigitableLine
from paysentineliq.domain.ingestion import VisualSignal
from paysentineliq.domain.receipt.analysis import analyze_receipt
from paysentineliq.domain.receipt.extraction import extract_receipt_fields
from tests.support.receipt_factory import build_receipt

pytestmark = pytest.mark.unit


def test_utility_line_exposes_blocks_dvs_and_structural_barcode() -> None:
    receipt = build_receipt()
    line = UtilityDigitableLine(receipt.line)

    assert line.blocks() == receipt.blocks
    assert line.barcode_digits() == receipt.barcode
    assert len(line.field_dvs()) == 4


def test_extracts_receipt_fields_from_formatted_text() -> None:
    receipt = build_receipt()

    fields = extract_receipt_fields(receipt.ocr_text())

    assert fields.line is not None
    assert fields.line.value == receipt.line
    assert fields.barcode is not None
    assert fields.barcode.value == receipt.barcode
    assert fields.issuer is not None
    assert fields.issuer.value == receipt.issuer
    assert fields.reference is not None
    assert fields.reference.value == "01/2026"
    assert fields.amount is not None
    assert fields.amount.value == Decimal("184.75")
    assert fields.due_date is not None
    assert fields.due_date.value == date(2026, 1, 15)


def test_legitimate_receipt_has_zero_subscore() -> None:
    fields = extract_receipt_fields(build_receipt().ocr_text())

    analysis = analyze_receipt(fields)

    assert analysis.subscore == 0
    assert analysis.evidence == ()
    assert "issuer_registry" in analysis.not_validated
    assert "dv_algorithm" in analysis.not_validated
    assert analysis.barcode_checked is True


def test_tampered_dv_is_critical() -> None:
    fields = extract_receipt_fields(build_receipt().with_tampered_dv().ocr_text())

    analysis = analyze_receipt(fields)

    assert "receipt_dv_invalid" in {item.rule_id for item in analysis.evidence}
    assert analysis.subscore >= 80


def test_tampered_barcode_is_critical() -> None:
    fields = extract_receipt_fields(build_receipt().with_tampered_barcode().ocr_text())

    analysis = analyze_receipt(fields)

    assert "receipt_barcode_mismatch" in {item.rule_id for item in analysis.evidence}
    assert analysis.subscore >= 80


def test_conflicting_amount_and_due_date_are_evidence() -> None:
    receipt = build_receipt().with_extra(
        "VALOR A PAGAR: R$ 999,00",
        "PAGUE ATE: 20/01/2026",
    )
    fields = extract_receipt_fields(receipt.ocr_text())

    analysis = analyze_receipt(fields)

    rules = {item.rule_id for item in analysis.evidence}
    assert "receipt_amount_inconsistent" in rules
    assert "receipt_due_date_inconsistent" in rules


def test_missing_issuer_is_not_entity_fraud() -> None:
    receipt = build_receipt().with_extra()
    text = receipt.ocr_text().replace(f"CONCESSIONARIA: {receipt.issuer}\n", "")
    fields = extract_receipt_fields(text)

    analysis = analyze_receipt(fields)

    rules = {item.rule_id for item in analysis.evidence}
    assert "receipt_issuer_missing" in rules
    assert "issuer_registry" in analysis.not_validated
    assert analysis.subscore < 80


def test_missing_amount_and_due_date_are_high_risk() -> None:
    receipt = build_receipt()
    text = "\n".join(
        line
        for line in receipt.ocr_text().splitlines()
        if "VALOR" not in line and "VENCIMENTO" not in line
    )
    fields = extract_receipt_fields(text)

    analysis = analyze_receipt(fields)

    rules = {item.rule_id for item in analysis.evidence}
    assert "receipt_amount_missing" in rules
    assert "receipt_due_date_missing" in rules


def test_summary_marks_receipt_and_has_no_due_factor() -> None:
    analysis = analyze_receipt(extract_receipt_fields(build_receipt().ocr_text()))

    summary = summary_from_receipt(analysis)

    assert summary.document_type == "receipt"
    assert summary.subscore == 0
    assert summary.amount_cents == 18475
    assert summary.due_factor is None
    assert summary.field_confidences


def test_visual_anomaly_raises_receipt_score() -> None:
    analysis = analyze_receipt(extract_receipt_fields(build_receipt().ocr_text()))
    summary = summary_from_receipt(analysis)
    service = FraudScoringService()

    clean = service.score(FraudScoringRequest(deterministic=summary))
    anomalous = service.score(
        FraudScoringRequest(
            deterministic=summary,
            visual_signals=(VisualSignal(name="ela", value=0.9, explanation="synthetic"),),
        ),
    )

    assert anomalous.score > clean.score
    assert anomalous.visual_component > clean.visual_component
