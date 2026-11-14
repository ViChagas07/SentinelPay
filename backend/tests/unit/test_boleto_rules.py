from datetime import timedelta

import pytest

from paysentineliq.domain.boleto.analysis import BarcodeRead, BoletoAnalysis, analyze_boleto
from paysentineliq.domain.boleto.bank_directory import BankDirectory, load_bank_directory
from paysentineliq.domain.boleto.extraction import (
    BoletoFields,
    ExtractedField,
    extract_boleto_fields,
)
from paysentineliq.domain.boleto.rules import (
    RULES,
    RuleDefinition,
    Severity,
    active_rules,
)
from tests.support.boleto_factory import build_boleto, format_date, format_line


def _directory() -> BankDirectory:
    return load_bank_directory()


def _analyze_text(text: str, barcode_read: BarcodeRead | None = None) -> BoletoAnalysis:
    directory = _directory()
    fields = extract_boleto_fields(text, bank_directory=directory)
    return analyze_boleto(fields, barcode_read=barcode_read, bank_directory=directory)


def _ids(analysis: BoletoAnalysis) -> list[str]:
    return [evidence.rule_id for evidence in analysis.evidence]


def test_valid_synthetic_boleto_scores_zero() -> None:
    boleto = build_boleto()

    analysis = _analyze_text(boleto.ocr_text())

    assert analysis.subscore == 0
    assert _ids(analysis) == []
    assert analysis.decoded is not None
    assert analysis.decoded.bank_code == "341"
    assert analysis.decoded.bank_name == "Banco Itaú S.A."
    assert analysis.decoded.amount.cents == 123456
    assert analysis.decoded.due_date == boleto.due_date
    assert analysis.barcode_read.status == "not_validated"
    assert "barcode_image_read" in analysis.not_validated
    assert "bacen_bank_registry" in analysis.not_validated
    assert "cip_title_registry" in analysis.not_validated
    assert "receita_tax_id_registry" in analysis.not_validated
    assert "due_date_cycle_reset" in analysis.not_validated
    assert "cpf_cnpj_dv_source" in analysis.not_validated


def test_invalid_field_dv_triggers_critical_floor() -> None:
    boleto = build_boleto()
    tampered = boleto.line[:9] + str((int(boleto.line[9]) + 1) % 10) + boleto.line[10:]
    text = boleto.ocr_text().replace(boleto.formatted_line, format_line(tampered))

    analysis = _analyze_text(text)

    assert _ids(analysis) == ["dv_invalid"]
    assert analysis.subscore == 80


def test_line_and_barcode_divergence_triggers_rule() -> None:
    boleto = build_boleto()
    other = build_boleto(free_field="9876543210987654321098765")

    analysis = _analyze_text(
        boleto.ocr_text(),
        barcode_read=BarcodeRead(status="read", digits=other.barcode),
    )

    assert _ids(analysis) == ["line_barcode_mismatch"]
    assert analysis.subscore == 80


def test_text_amount_divergence_triggers_rule() -> None:
    boleto = build_boleto()
    text = boleto.ocr_text().replace("R$ 1.234,56", "R$ 1.234,57")

    analysis = _analyze_text(text)

    assert _ids(analysis) == ["amount_mismatch"]
    assert analysis.subscore == 80


def test_text_due_date_divergence_triggers_rule() -> None:
    boleto = build_boleto()
    assert boleto.due_date is not None
    text = boleto.ocr_text().replace(
        format_date(boleto.due_date),
        format_date(boleto.due_date + timedelta(days=1)),
    )

    analysis = _analyze_text(text)

    assert _ids(analysis) == ["due_date_mismatch"]
    assert analysis.subscore == 30


def test_bank_header_divergence_triggers_rule() -> None:
    boleto = build_boleto()
    text = boleto.ocr_text().replace(boleto.header, "BANCO DO BRASIL S.A. 001")

    analysis = _analyze_text(text)

    assert _ids(analysis) == ["bank_header_mismatch"]
    assert analysis.subscore == 30


def test_unknown_bank_code_triggers_rule() -> None:
    boleto = build_boleto(bank="999")

    analysis = _analyze_text(boleto.ocr_text())

    assert _ids(analysis) == ["bank_code_unknown"]
    assert analysis.subscore == 20


def test_unsupported_currency_triggers_rule() -> None:
    boleto = build_boleto(currency="1")

    analysis = _analyze_text(boleto.ocr_text())

    assert _ids(analysis) == ["currency_unsupported"]
    assert analysis.subscore == 15


def test_invalid_tax_id_triggers_rule() -> None:
    boleto = build_boleto(beneficiary_tax_id="11.222.333/0001-80")

    analysis = _analyze_text(boleto.ocr_text())

    assert _ids(analysis) == ["tax_id_invalid"]
    assert analysis.subscore == 25
    assert analysis.evidence[0].details["masked"].endswith("-80")


def test_missing_beneficiary_triggers_illegible_rule() -> None:
    boleto = build_boleto()
    text = boleto.ocr_text().replace("BENEFICIARIO: PAGAMENTOS SINTETICOS LTDA\n", "")

    analysis = _analyze_text(text)

    assert _ids(analysis) == ["field_illegible"]
    assert analysis.subscore == 10
    assert "beneficiary" in analysis.evidence[0].details["fields"]


def test_barcode_unreadable_triggers_rule() -> None:
    boleto = build_boleto()

    analysis = _analyze_text(
        boleto.ocr_text(),
        barcode_read=BarcodeRead(status="not_found", reason="barcode_not_found"),
    )

    assert _ids(analysis) == ["barcode_unreadable"]
    assert analysis.subscore == 10
    assert "barcode_image_read" in analysis.not_validated


def test_utility_line_is_not_verifiable_and_scores_zero() -> None:
    text = "\n".join(
        [
            "BANCO DO BRASIL S.A. 001",
            "VALOR DO DOCUMENTO: R$ 10,00",
            "VENCIMENTO: 01/02/2022",
            "BENEFICIARIO: ORGAO PUBLICO",
            "CNPJ: 11.222.333/0001-81",
            "LINHA DIGITAVEL: " + "9" * 48,
        ],
    )

    analysis = _analyze_text(text)

    assert _ids(analysis) == ["utility_line_not_verifiable"]
    assert analysis.subscore == 0
    assert analysis.decoded is None
    assert "utility_line_layout" in analysis.not_validated


def test_score_is_capped_and_evidence_is_sorted() -> None:
    boleto = build_boleto(beneficiary_tax_id="11.222.333/0001-80")
    assert boleto.due_date is not None
    text = (
        boleto.ocr_text()
        .replace("R$ 1.234,56", "R$ 1.234,57")
        .replace(
            format_date(boleto.due_date),
            format_date(boleto.due_date + timedelta(days=1)),
        )
    )

    analysis = _analyze_text(text)

    assert analysis.subscore == 100
    assert _ids(analysis) == ["amount_mismatch", "due_date_mismatch", "tax_id_invalid"]


def test_rules_without_source_are_excluded() -> None:
    source_less = RuleDefinition(
        id="source_less",
        version="1",
        severity=Severity.CRITICAL,
        weight=100,
        source=None,
        message_key="boleto.source_less",
    )

    active = active_rules((*RULES, source_less))

    assert source_less not in active
    for rule in active:
        assert rule.source is not None
        assert rule.source.startswith("knowledge/febraban/") or rule.source.startswith(
            "knowledge/layouts/",
        )


def test_missing_line_triggers_critical_rule() -> None:
    analysis = analyze_boleto(BoletoFields(), bank_directory=_directory())

    assert _ids(analysis) == ["line_invalid"]
    assert analysis.subscore == 80
    assert analysis.decoded is None


def test_invalid_line_length_triggers_rule() -> None:
    fields = BoletoFields(line=ExtractedField(value="1" * 46, confidence=1.0))

    analysis = analyze_boleto(fields, bank_directory=_directory())

    assert _ids(analysis) == ["line_invalid"]
    assert analysis.evidence[0].details["reason"] == "length"


async def test_barcode_without_digits_triggers_unreadable_rule() -> None:
    boleto = build_boleto()

    analysis = _analyze_text(
        boleto.ocr_text(),
        barcode_read=BarcodeRead(status="read", digits=None),
    )

    assert _ids(analysis) == ["barcode_unreadable"]
    assert analysis.subscore == 10


def test_barcode_with_invalid_digits_triggers_unreadable_rule() -> None:
    boleto = build_boleto()

    analysis = _analyze_text(
        boleto.ocr_text(),
        barcode_read=BarcodeRead(status="read", digits="1" * 43),
    )

    assert _ids(analysis) == ["barcode_unreadable"]
    assert analysis.subscore == 10


def test_text_barcode_mismatch_triggers_rule() -> None:
    boleto = build_boleto()
    other = build_boleto(free_field="9876543210987654321098765")
    text = boleto.ocr_text() + f"\nCODIGO DE BARRAS: {other.barcode}"

    analysis = _analyze_text(text)

    assert _ids(analysis) == ["line_barcode_mismatch"]
    assert analysis.subscore == 80


def test_low_confidence_text_barcode_is_ignored() -> None:
    boleto = build_boleto()
    text = boleto.ocr_text() + f"\nNUMERO: {boleto.barcode}"

    analysis = _analyze_text(text)

    assert analysis.subscore == 0
    assert "barcode_text_low_confidence" in analysis.not_validated


def test_declared_absent_due_date_conflicts_with_decoded_factor() -> None:
    boleto = build_boleto()
    assert boleto.due_date is not None
    text = (
        boleto.ocr_text().replace(f"VENCIMENTO: {format_date(boleto.due_date)}\n", "")
        + "SEM VENCIMENTO"
    )

    analysis = _analyze_text(text)

    assert _ids(analysis) == ["due_date_mismatch"]
    assert analysis.subscore == 30


def test_missing_due_date_without_absence_marker_is_illegible() -> None:
    boleto = build_boleto()
    assert boleto.due_date is not None
    text = boleto.ocr_text().replace(f"VENCIMENTO: {format_date(boleto.due_date)}\n", "")

    analysis = _analyze_text(text)

    assert _ids(analysis) == ["field_illegible"]
    assert "due_date" in analysis.evidence[0].details["fields"]


def test_invalid_payer_tax_id_triggers_rule() -> None:
    boleto = build_boleto(payer_tax_id="123.456.789-08")

    analysis = _analyze_text(boleto.ocr_text())

    assert _ids(analysis) == ["tax_id_invalid"]
    assert analysis.subscore == 25
    assert analysis.evidence[0].details["roles"] == "payer"


def test_invalid_additional_tax_id_triggers_rule() -> None:
    boleto = build_boleto(beneficiary_tax_id="11.222.333/0001-80")
    text = boleto.ocr_text().replace("BENEFICIARIO: PAGAMENTOS SINTETICOS LTDA\n", "")

    analysis = _analyze_text(text)

    assert set(_ids(analysis)) == {"field_illegible", "tax_id_invalid"}
    tax_evidence = next(
        evidence for evidence in analysis.evidence if evidence.rule_id == "tax_id_invalid"
    )
    assert "additional_1" in tax_evidence.details["roles"]


def test_valid_text_barcode_keeps_score_zero() -> None:
    boleto = build_boleto(include_barcode_text=True)

    analysis = _analyze_text(boleto.ocr_text())

    assert analysis.subscore == 0
    assert analysis.barcode_read.status == "not_validated"


def test_non_numeric_bank_line_triggers_rule() -> None:
    fields = BoletoFields(line=ExtractedField(value="A" * 47, confidence=1.0))

    analysis = analyze_boleto(fields, bank_directory=_directory())

    assert _ids(analysis) == ["line_invalid"]
    assert analysis.evidence[0].details["reason"] == "non_numeric"


def test_non_numeric_utility_line_triggers_rule() -> None:
    fields = BoletoFields(line=ExtractedField(value="A" * 48, confidence=1.0))

    analysis = analyze_boleto(fields, bank_directory=_directory())

    assert _ids(analysis) == ["line_invalid"]
    assert analysis.evidence[0].details["reason"] == "non_numeric"


def test_barcode_only_decode_uses_barcode_data() -> None:
    boleto = build_boleto()
    fields = BoletoFields(barcode=ExtractedField(value=boleto.barcode, confidence=0.9))

    analysis = analyze_boleto(fields, bank_directory=_directory())

    assert "line_invalid" in _ids(analysis)
    assert analysis.decoded is not None
    assert analysis.decoded.amount.cents == 123456
    assert analysis.decoded.due_date == boleto.due_date


def test_invalid_text_barcode_triggers_unreadable_rule() -> None:
    boleto = build_boleto()
    fields = BoletoFields(
        line=ExtractedField(value=boleto.line, confidence=1.0),
        barcode=ExtractedField(value="1" * 43, confidence=0.9),
    )

    analysis = analyze_boleto(fields, bank_directory=_directory())

    assert "barcode_unreadable" in _ids(analysis)
    evidence = next(item for item in analysis.evidence if item.rule_id == "barcode_unreadable")
    assert evidence.details["reason"] == "text_invalid"


def test_zero_factor_with_printed_due_date_triggers_rule() -> None:
    boleto = build_boleto(factor=0)
    text = boleto.ocr_text() + "\nVENCIMENTO: 01/01/2022"

    analysis = _analyze_text(text)

    assert _ids(analysis) == ["due_date_mismatch"]
    assert analysis.subscore == 30


def test_missing_amount_is_illegible() -> None:
    boleto = build_boleto()
    text = boleto.ocr_text().replace("VALOR DO DOCUMENTO: R$ 1.234,56\n", "")

    analysis = _analyze_text(text)

    assert _ids(analysis) == ["field_illegible"]
    assert "amount" in analysis.evidence[0].details["fields"]


def test_missing_bank_header_is_illegible() -> None:
    boleto = build_boleto()
    text = "\n".join(boleto.ocr_text().splitlines()[1:])

    analysis = _analyze_text(text)

    assert _ids(analysis) == ["field_illegible"]
    assert "bank_header" in analysis.evidence[0].details["fields"]


def test_rule_definition_validates_fields() -> None:
    with pytest.raises(ValueError):
        RuleDefinition(
            id="",
            version="1",
            severity=Severity.HIGH,
            weight=1,
            source="knowledge/febraban/manual_febraban_v1.pdf#1",
            message_key="boleto.rule",
        )
    with pytest.raises(ValueError):
        RuleDefinition(
            id="rule",
            version="",
            severity=Severity.HIGH,
            weight=1,
            source="knowledge/febraban/manual_febraban_v1.pdf#1",
            message_key="boleto.rule",
        )
    with pytest.raises(ValueError):
        RuleDefinition(
            id="rule",
            version="1",
            severity=Severity.HIGH,
            weight=-1,
            source="knowledge/febraban/manual_febraban_v1.pdf#1",
            message_key="boleto.rule",
        )
    with pytest.raises(ValueError):
        RuleDefinition(
            id="rule",
            version="1",
            severity=Severity.HIGH,
            weight=1,
            source="knowledge/febraban/manual_febraban_v1.pdf#1",
            message_key="",
        )


def test_barcode_only_invalid_general_dv_triggers_rule() -> None:
    boleto = build_boleto()
    tampered = boleto.barcode[:4] + str((int(boleto.barcode[4]) + 1) % 10) + boleto.barcode[5:]
    fields = BoletoFields(barcode=ExtractedField(value=tampered, confidence=0.9))

    analysis = analyze_boleto(fields, bank_directory=_directory())

    assert "dv_invalid" in _ids(analysis)
    evidence = next(item for item in analysis.evidence if item.rule_id == "dv_invalid")
    assert evidence.details["fields"] == "general"


@pytest.mark.parametrize(
    ("case", "expected_rule", "expected_score"),
    [
        ("valid", None, 0),
        ("dv", "dv_invalid", 80),
        ("amount", "amount_mismatch", 80),
        ("due_date", "due_date_mismatch", 30),
        ("tax_id", "tax_id_invalid", 25),
    ],
)
def test_rule_matrix_with_one_alteration_at_a_time(
    case: str,
    expected_rule: str | None,
    expected_score: int,
) -> None:
    tax_id = "11.222.333/0001-80" if case == "tax_id" else "11.222.333/0001-81"
    boleto = build_boleto(beneficiary_tax_id=tax_id)
    text = boleto.ocr_text()

    if case == "dv":
        tampered = boleto.line[:9] + str((int(boleto.line[9]) + 1) % 10) + boleto.line[10:]
        text = text.replace(boleto.formatted_line, format_line(tampered))
    elif case == "amount":
        text = text.replace("R$ 1.234,56", "R$ 1.234,57")
    elif case == "due_date":
        assert boleto.due_date is not None
        text = text.replace(
            format_date(boleto.due_date),
            format_date(boleto.due_date + timedelta(days=1)),
        )

    analysis = _analyze_text(text)

    if expected_rule is None:
        assert _ids(analysis) == []
    else:
        assert _ids(analysis) == [expected_rule]
    assert analysis.subscore == expected_score


def test_low_confidence_due_date_is_illegible_not_mismatch() -> None:
    boleto = build_boleto()
    assert boleto.due_date is not None
    text = boleto.ocr_text().replace(
        f"VENCIMENTO: {format_date(boleto.due_date)}",
        "01/01/2022",
    )

    analysis = _analyze_text(text)

    assert _ids(analysis) == ["field_illegible"]
    assert "due_date" in analysis.evidence[0].details["fields"]
