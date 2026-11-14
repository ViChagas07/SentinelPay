from datetime import date
from decimal import Decimal

import pytest

from paysentineliq.application.queries.fraud_features import (
    FEATURE_NAMES,
    build_feature_vector,
    summary_from_boleto,
    summary_from_payslip,
    visual_score,
)
from paysentineliq.domain.boleto.analysis import analyze_boleto
from paysentineliq.domain.boleto.bank_directory import load_bank_directory
from paysentineliq.domain.boleto.extraction import extract_boleto_fields
from paysentineliq.domain.ingestion import VisualSignal
from paysentineliq.domain.payslip.analysis import analyze_payslip
from paysentineliq.domain.payslip.extraction import extract_payslip_fields
from paysentineliq.domain.scoring import (
    DeterministicSummary,
    EvidenceSummary,
    SeverityLevel,
)
from tests.support.boleto_factory import build_boleto
from tests.support.payslip_factory import SyntheticPayslip
from tests.support.regulatory_factory import synthetic_regulatory_tables

pytestmark = pytest.mark.unit


def _summary(
    *,
    subscore: int = 0,
    evidence: tuple[EvidenceSummary, ...] = (),
) -> DeterministicSummary:
    return DeterministicSummary(
        document_type="boleto",
        subscore=subscore,
        evidence=evidence,
        field_confidences=(0.95, 0.9, 0.8),
        not_validated_count=0,
        amount_cents=123456,
        due_factor=9000,
        barcode_read=None,
    )


def test_feature_names_are_unique_and_include_rule_indicators() -> None:
    assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES))
    assert "subscore_norm" in FEATURE_NAMES
    assert "visual_max" in FEATURE_NAMES
    assert "rule_dv_invalid" in FEATURE_NAMES
    assert "rule_net_mismatch" in FEATURE_NAMES


def test_build_feature_vector_is_numeric_and_fixed_order() -> None:
    vector = build_feature_vector(_summary(), ())

    assert len(vector) == len(FEATURE_NAMES)
    assert all(isinstance(value, float) for value in vector)


def test_visual_features_use_count_max_and_mean() -> None:
    signals = (
        VisualSignal(name="a", value=0.2, explanation="a"),
        VisualSignal(name="b", value=0.8, explanation="b"),
    )

    vector = build_feature_vector(_summary(), signals)
    values = dict(zip(FEATURE_NAMES, vector, strict=True))

    assert values["visual_count"] == 2.0
    assert values["visual_max"] == 0.8
    assert values["visual_mean"] == 0.5
    assert visual_score(signals) == 0.8
    assert visual_score(()) == 0.0


def test_rule_indicator_and_critical_count_from_evidence() -> None:
    summary = _summary(
        subscore=80,
        evidence=(
            EvidenceSummary(
                rule_id="dv_invalid",
                severity=SeverityLevel.CRITICAL,
                weight=70,
            ),
        ),
    )

    values = dict(zip(FEATURE_NAMES, build_feature_vector(summary, ()), strict=True))

    assert values["subscore_norm"] == 0.8
    assert values["critical_count"] == 1.0
    assert values["rule_dv_invalid"] == 1.0
    assert values["weighted_sum_norm"] == 0.7


def test_summary_from_boleto_preserves_numeric_context() -> None:
    boleto = build_boleto()
    directory = load_bank_directory()
    analysis = analyze_boleto(
        extract_boleto_fields(boleto.ocr_text(), bank_directory=directory),
        bank_directory=directory,
    )

    summary = summary_from_boleto(analysis)

    assert summary.document_type == "boleto"
    assert summary.subscore == 0
    assert summary.amount_cents == 123456
    assert summary.due_factor == 9000
    assert summary.barcode_read is None
    assert summary.field_confidences
    assert all(0.0 <= value <= 1.0 for value in summary.field_confidences)


def test_summary_from_payslip_preserves_ratios_and_items() -> None:
    analysis = analyze_payslip(
        extract_payslip_fields(SyntheticPayslip().ocr_text()),
        regulatory=synthetic_regulatory_tables(),
        reference_date=date(2024, 6, 1),
    )

    summary = summary_from_payslip(analysis)

    assert summary.document_type == "payslip"
    assert summary.item_count == 4
    assert summary.total_earnings == Decimal("2100.00")
    assert summary.total_deductions == Decimal("407.00")
    assert summary.net == Decimal("1693.00")
    assert summary.field_confidences
    assert summary.has_unknown_items is False


def test_features_do_not_include_raw_text_or_pii() -> None:
    forbidden = ("raw", "text", "name", "cpf", "cnpj", "email", "address")
    base_features = [feature for feature in FEATURE_NAMES if not feature.startswith("rule_")]
    assert not any(token in feature for feature in base_features for token in forbidden)
    summary = _summary(
        evidence=(
            EvidenceSummary(
                rule_id="employee_cpf_invalid",
                severity=SeverityLevel.HIGH,
                weight=25,
            ),
        ),
    )
    vector = build_feature_vector(summary, ())
    assert all(isinstance(value, float) for value in vector)
