from datetime import date
from decimal import Decimal

import pytest

from paysentineliq.domain.payslip.analysis import PayslipAnalysis, analyze_payslip
from paysentineliq.domain.payslip.extraction import extract_payslip_fields
from paysentineliq.domain.payslip.regulatory import RegulatoryTables, load_regulatory_tables
from paysentineliq.domain.payslip.rules import (
    RULES,
    EvidenceStatus,
    RuleDefinition,
    Severity,
    active_rules,
)
from tests.support.payslip_factory import SyntheticPayslip
from tests.support.regulatory_factory import synthetic_regulatory_tables

pytestmark = pytest.mark.unit

_REFERENCE_DATE = date(2024, 6, 1)


def _analyze(
    text: str,
    *,
    regulatory: RegulatoryTables | None = None,
    reference_date: date = _REFERENCE_DATE,
) -> PayslipAnalysis:
    return analyze_payslip(
        extract_payslip_fields(text),
        regulatory=regulatory or synthetic_regulatory_tables(),
        reference_date=reference_date,
    )


def _ids(analysis: PayslipAnalysis) -> list[str]:
    return [evidence.rule_id for evidence in analysis.evidence]


def _triggered(analysis: PayslipAnalysis) -> list[str]:
    return [
        evidence.rule_id
        for evidence in analysis.evidence
        if evidence.status is EvidenceStatus.TRIGGERED
    ]


def test_valid_payslip_with_synthetic_tables_scores_zero() -> None:
    analysis = _analyze(SyntheticPayslip().ocr_text())

    assert analysis.subscore == 0
    assert analysis.evidence == ()
    assert analysis.payslip is not None
    assert analysis.payslip.employee_cpf_valid is True
    assert analysis.payslip.earnings_sum == Decimal("2100.00")
    assert analysis.payslip.deductions_sum == Decimal("407.00")
    assert analysis.fields.employee_cpf_masked is not None
    assert analysis.fields.employee_cpf_masked.value == "***.***.***-09"
    assert "12345678909" not in repr(analysis)
    assert analysis.layout_confidence == 1.0


def test_valid_payslip_without_official_tables_does_not_raise_risk() -> None:
    analysis = _analyze(
        SyntheticPayslip().ocr_text(),
        regulatory=load_regulatory_tables(),
    )

    assert analysis.subscore == 0
    assert analysis.evidence
    assert all(evidence.status is EvidenceStatus.NOT_VERIFIABLE for evidence in analysis.evidence)
    assert all(evidence.weight == 0 for evidence in analysis.evidence)
    assert all(evidence.severity is Severity.INFO for evidence in analysis.evidence)
    assert "inss_table_missing" in analysis.not_validated
    assert "irrf_table_missing" in analysis.not_validated
    assert "minimum_wage_table_missing" in analysis.not_validated
    assert "overtime_parameter_missing" in analysis.not_validated


def test_earnings_total_mismatch_triggers_alone() -> None:
    analysis = _analyze(
        SyntheticPayslip(
            total_earnings="2.101,00",
            inss="330,30",
            irrf="77,07",
            total_deductions="407,37",
            net="1.693,63",
            irrf_base="1.770,70",
        ).ocr_text(),
    )

    assert _ids(analysis) == ["earnings_total_mismatch"]
    assert analysis.subscore == 25


def test_deductions_total_mismatch_triggers_alone() -> None:
    analysis = _analyze(
        SyntheticPayslip(
            total_deductions="408,00",
            net="1.692,00",
        ).ocr_text(),
    )

    assert _ids(analysis) == ["deductions_total_mismatch"]
    assert analysis.subscore == 25


def test_net_mismatch_triggers_alone() -> None:
    analysis = _analyze(SyntheticPayslip(net="1.692,00").ocr_text())

    assert _ids(analysis) == ["net_mismatch"]
    assert analysis.subscore == 30


def test_net_above_earnings_triggers_critical_floor() -> None:
    analysis = _analyze(SyntheticPayslip(net="2.200,00").ocr_text())

    assert _ids(analysis) == ["net_exceeds_earnings"]
    assert analysis.subscore == 80


def test_inss_mismatch_triggers_alone() -> None:
    analysis = _analyze(
        SyntheticPayslip(
            inss="320,00",
            total_deductions="397,00",
            net="1.703,00",
        ).ocr_text(),
    )

    assert _ids(analysis) == ["inss_mismatch"]
    assert analysis.subscore == 30


def test_irrf_mismatch_triggers_alone() -> None:
    analysis = _analyze(
        SyntheticPayslip(
            irrf="70,00",
            total_deductions="400,00",
            net="1.700,00",
        ).ocr_text(),
    )

    assert _ids(analysis) == ["irrf_mismatch"]
    assert analysis.subscore == 30


def test_base_below_minimum_triggers_alone() -> None:
    text = (
        SyntheticPayslip(base_salary="900,00")
        .ocr_text()
        .replace(
            "001 SALARIO BASE 900,00",
            "001 SALARIO BASE 900,00\n003 BONUS 1.100,00",
        )
    )

    analysis = _analyze(text)

    assert _ids(analysis) == ["base_below_minimum"]
    assert analysis.subscore == 30


def test_overtime_below_minimum_triggers_alone() -> None:
    analysis = _analyze(SyntheticPayslip(overtime_percent="40%").ocr_text())

    assert _ids(analysis) == ["overtime_below_minimum"]
    assert analysis.subscore == 20


def test_future_competency_triggers_without_high_risk() -> None:
    analysis = _analyze(SyntheticPayslip(competency="01/2099").ocr_text())

    triggered = _triggered(analysis)
    assert triggered == ["competency_implausible"]
    assert analysis.subscore == 10
    assert all(
        evidence.severity not in (Severity.CRITICAL, Severity.HIGH)
        for evidence in analysis.evidence
    )
    assert "inss_table_missing" in analysis.not_validated


def test_invalid_employer_cnpj_triggers_alone() -> None:
    analysis = _analyze(SyntheticPayslip(employer_cnpj="11.222.333/0001-80").ocr_text())

    assert _ids(analysis) == ["employer_cnpj_invalid"]
    assert analysis.subscore == 25


def test_invalid_employee_cpf_triggers_alone_and_masks_cpf() -> None:
    analysis = _analyze(SyntheticPayslip(employee_cpf="123.456.789-08").ocr_text())

    assert _ids(analysis) == ["employee_cpf_invalid"]
    assert analysis.subscore == 25
    assert analysis.fields.employee_cpf_masked is not None
    assert analysis.fields.employee_cpf_masked.value == "***.***.***-08"
    assert "12345678908" not in repr(analysis)


def test_duplicate_item_triggers_alone() -> None:
    text = (
        SyntheticPayslip(
            total_earnings="4.100,00",
            inss="600,00",
            irrf="400,00",
            total_deductions="1.000,00",
            net="3.100,00",
            irrf_base="3.500,00",
        )
        .ocr_text()
        .replace(
            "001 SALARIO BASE 2.000,00",
            "001 SALARIO BASE 2.000,00\n001 SALARIO BASE 2.000,00",
        )
    )

    analysis = _analyze(text)

    assert _ids(analysis) == ["duplicate_item"]
    assert analysis.subscore == 25


def test_rounding_incoherent_triggers_alone() -> None:
    analysis = _analyze(
        SyntheticPayslip(
            overtime_amount="100,005",
            total_earnings="2.100,01",
            inss="330,00",
            irrf="77,00",
            total_deductions="407,00",
            net="1.693,01",
            irrf_base="1.770,01",
        ).ocr_text(),
    )

    assert _ids(analysis) == ["rounding_incoherent"]
    assert analysis.subscore == 5


def test_missing_employee_name_triggers_illegible_rule() -> None:
    text = (
        SyntheticPayslip()
        .ocr_text()
        .replace(
            "FUNCIONARIO: CLIENTE SINTETICO\n",
            "",
        )
    )

    analysis = _analyze(text)

    assert _ids(analysis) == ["field_illegible"]
    assert analysis.subscore == 10
    assert "employee_name" in analysis.evidence[0].details["fields"]


def test_unknown_layout_reduces_confidence_without_high_risk() -> None:
    text = "\n".join(
        [
            "2.000,00",
            "100,00",
            "2.100,00",
            "300,00",
            "80,00",
            "380,00",
            "1.720,00",
        ],
    )

    analysis = _analyze(text, regulatory=load_regulatory_tables())

    assert analysis.layout_confidence < 0.5
    assert "payslip_layout_unknown" in analysis.not_validated
    assert analysis.subscore <= 10
    assert all(
        evidence.severity not in (Severity.CRITICAL, Severity.HIGH)
        for evidence in analysis.evidence
    )


def test_rules_without_source_are_excluded() -> None:
    source_less = RuleDefinition(
        id="source_less",
        version="1",
        severity=Severity.CRITICAL,
        weight=100,
        source=None,
        message_key="payslip.source_less",
    )

    active = active_rules((*RULES, source_less))

    assert source_less not in active
    for rule in active:
        assert rule.source is not None
        assert rule.source.startswith(
            ("knowledge/fraud_patterns/", "data/regulatory/"),
        )


def test_unknown_item_makes_totals_not_verifiable() -> None:
    text = (
        SyntheticPayslip()
        .ocr_text()
        .replace(
            "COMPETENCIA: 05/2024\nPROVENTOS",
            "COMPETENCIA: 05/2024\nITEM MISTERIOSO 50,00\nPROVENTOS",
        )
    )

    analysis = _analyze(text)

    assert analysis.subscore == 0
    statuses = {evidence.rule_id: evidence.status for evidence in analysis.evidence}
    assert statuses["earnings_total_mismatch"] is EvidenceStatus.NOT_VERIFIABLE
    assert statuses["deductions_total_mismatch"] is EvidenceStatus.NOT_VERIFIABLE
    assert statuses["net_mismatch"] is EvidenceStatus.NOT_VERIFIABLE


def test_missing_irrf_base_is_not_verifiable() -> None:
    text = SyntheticPayslip().ocr_text().replace("BASE IRRF 1.770,00\n", "")

    analysis = _analyze(text)

    assert analysis.subscore == 0
    assert "irrf_base_missing" in analysis.not_validated
    irrf = next(evidence for evidence in analysis.evidence if evidence.rule_id == "irrf_mismatch")
    assert irrf.status is EvidenceStatus.NOT_VERIFIABLE


def test_missing_base_salary_is_illegible_and_not_verifiable() -> None:
    text = (
        SyntheticPayslip(
            total_earnings="100,00",
            inss="10,00",
            irrf="0,00",
            total_deductions="10,00",
            net="90,00",
            irrf_base="90,00",
        )
        .ocr_text()
        .replace("001 SALARIO BASE 2.000,00\n", "")
    )

    analysis = _analyze(text)

    assert _triggered(analysis) == ["field_illegible"]
    assert analysis.subscore == 10
    assert "base_salary_missing" in analysis.not_validated
    illegible = next(
        evidence for evidence in analysis.evidence if evidence.rule_id == "field_illegible"
    )
    assert "base_salary" in illegible.details["fields"]


def test_missing_competency_with_overtime_is_not_verifiable() -> None:
    text = SyntheticPayslip().ocr_text().replace("COMPETENCIA: 05/2024\n", "")

    analysis = _analyze(text)

    assert _triggered(analysis) == ["field_illegible"]
    assert analysis.subscore == 10
    illegible = next(
        evidence for evidence in analysis.evidence if evidence.rule_id == "field_illegible"
    )
    assert "competency" in illegible.details["fields"]


def test_overtime_without_percent_is_not_verifiable() -> None:
    text = (
        SyntheticPayslip()
        .ocr_text()
        .replace(
            "HORAS EXTRAS 50% 100,00",
            "HORAS EXTRAS 100,00",
        )
    )

    analysis = _analyze(text)

    assert analysis.subscore == 0
    assert "overtime_percent_missing" in analysis.not_validated
    overtime = next(
        evidence for evidence in analysis.evidence if evidence.rule_id == "overtime_below_minimum"
    )
    assert overtime.status is EvidenceStatus.NOT_VERIFIABLE
