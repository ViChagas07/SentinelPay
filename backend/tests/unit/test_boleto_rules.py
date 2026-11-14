from datetime import timedelta

from paysentineliq.domain.boleto.analysis import BarcodeRead, BoletoAnalysis, analyze_boleto
from paysentineliq.domain.boleto.bank_directory import BankDirectory, load_bank_directory
from paysentineliq.domain.boleto.extraction import extract_boleto_fields
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
