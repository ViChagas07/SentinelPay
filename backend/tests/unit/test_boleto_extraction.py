from datetime import date
from decimal import Decimal

from paysentineliq.domain.boleto.bank_directory import BankDirectory, load_bank_directory
from paysentineliq.domain.boleto.extraction import extract_boleto_fields
from paysentineliq.domain.boleto.tax_id import Cnpj, Cpf
from tests.support.boleto_factory import build_boleto


def _directory() -> BankDirectory:
    return load_bank_directory()


def test_extracts_valid_synthetic_fields_with_confidence() -> None:
    boleto = build_boleto()
    fields = extract_boleto_fields(boleto.ocr_text(), bank_directory=_directory())

    assert fields.line is not None
    assert fields.line.value == boleto.line
    assert fields.line.confidence == 1.0
    assert fields.amount is not None
    assert fields.amount.value == Decimal("1234.56")
    assert fields.amount.confidence == 1.0
    assert fields.due_date is not None
    assert fields.due_date.value == date(2022, 5, 29)
    assert fields.due_date.confidence == 1.0
    assert fields.beneficiary is not None
    assert fields.beneficiary.value == "PAGAMENTOS SINTETICOS LTDA"
    assert fields.beneficiary.confidence >= 0.9
    assert fields.beneficiary_tax_id is not None
    assert isinstance(fields.beneficiary_tax_id.value, Cnpj)
    assert fields.beneficiary_tax_id.value.is_valid
    assert fields.payer_tax_id is not None
    assert isinstance(fields.payer_tax_id.value, Cpf)
    assert fields.payer_tax_id.value.is_valid
    assert fields.bank_header is not None
    assert fields.bank_header.value.code == "341"
    assert fields.bank_header.confidence >= 0.9
    assert fields.barcode is None


def test_normalizes_ocr_confusions_and_reduces_confidence() -> None:
    boleto = build_boleto()
    confused_line = (
        boleto.formatted_line.replace("0", "O", 2).replace("1", "I", 1).replace("1", "l", 1)
    )
    text = boleto.ocr_text().replace(boleto.formatted_line, confused_line)

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.line is not None
    assert fields.line.value == boleto.line
    assert 0.5 <= fields.line.confidence < 1.0


def test_extracts_barcode_text_when_labeled() -> None:
    boleto = build_boleto(include_barcode_text=True)

    fields = extract_boleto_fields(boleto.ocr_text(), bank_directory=_directory())

    assert fields.barcode is not None
    assert fields.barcode.value == boleto.barcode
    assert fields.barcode.confidence >= 0.9


def test_extracts_split_line_from_two_ocr_lines() -> None:
    boleto = build_boleto()
    parts = boleto.formatted_line.split()
    split_line = " ".join(parts[:4]) + "\n" + " ".join(parts[4:])
    text = boleto.ocr_text().replace(boleto.formatted_line, split_line)

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.line is not None
    assert fields.line.value == boleto.line
    assert 0.5 <= fields.line.confidence < 1.0


def test_handles_absence_of_due_date() -> None:
    boleto = build_boleto(factor=0)
    text = boleto.ocr_text() + "\nSEM VENCIMENTO"

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.due_date is None
    assert fields.due_date_absent


def test_prefers_due_date_over_issue_date() -> None:
    boleto = build_boleto()
    text = boleto.ocr_text().replace(
        boleto.formatted_line,
        "EMISSAO: 01/01/2022\n" + boleto.formatted_line,
    )

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.due_date is not None
    assert fields.due_date.value == boleto.due_date
    assert fields.due_date.confidence == 1.0


def test_extracts_unformatted_tax_id_with_label() -> None:
    boleto = build_boleto()
    text = boleto.ocr_text().replace("11.222.333/0001-81", "11222333000181")

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.beneficiary_tax_id is not None
    assert fields.beneficiary_tax_id.value.digits == "11222333000181"
    assert fields.beneficiary_tax_id.confidence >= 0.8


def test_does_not_treat_line_tail_as_tax_id() -> None:
    boleto = build_boleto()
    text = boleto.ocr_text().replace("CNPJ: 11.222.333/0001-81\n", "")

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.beneficiary_tax_id is None
    assert fields.additional_tax_ids == ()


def test_extracts_unknown_bank_code_from_header() -> None:
    boleto = build_boleto(bank="999")

    fields = extract_boleto_fields(boleto.ocr_text(), bank_directory=_directory())

    assert fields.bank_header is not None
    assert fields.bank_header.value.code == "999"
    assert fields.bank_header.value.name == "BANCO 999"


def test_amount_without_currency_symbol_still_parses() -> None:
    boleto = build_boleto()
    text = boleto.ocr_text().replace("R$ 1.234,56", "1234,56")

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.amount is not None
    assert fields.amount.value == Decimal("1234.56")


def test_utility_line_is_extracted_structurally() -> None:
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

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.line is not None
    assert len(fields.line.value) == 48


def test_extracts_role_name_from_next_line() -> None:
    boleto = build_boleto()
    text = boleto.ocr_text().replace(
        "BENEFICIARIO: PAGAMENTOS SINTETICOS LTDA",
        "BENEFICIARIO:\nPAGAMENTOS SINTETICOS LTDA",
    )

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.beneficiary is not None
    assert fields.beneficiary.value == "PAGAMENTOS SINTETICOS LTDA"
    assert fields.beneficiary.confidence == 0.8


def test_line_without_label_has_lower_confidence() -> None:
    boleto = build_boleto()
    text = boleto.ocr_text().replace("LINHA DIGITAVEL: ", "")

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.line is not None
    assert fields.line.value == boleto.line
    assert fields.line.confidence == 0.95


def test_invalid_calendar_date_is_ignored() -> None:
    boleto = build_boleto()
    assert boleto.due_date is not None
    text = boleto.ocr_text().replace(
        boleto.due_date.strftime("%d/%m/%Y"),
        "31/02/2022",
    )

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.due_date is None


def test_formatted_tax_id_without_label_uses_current_role() -> None:
    boleto = build_boleto()
    text = boleto.ocr_text().replace("CNPJ: 11.222.333/0001-81", "11.222.333/0001-81")

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.beneficiary_tax_id is not None
    assert fields.beneficiary_tax_id.value.digits == "11222333000181"
    assert fields.beneficiary_tax_id.confidence == 0.8


def test_amount_without_label_has_lower_confidence() -> None:
    boleto = build_boleto()
    text = boleto.ocr_text().replace("VALOR DO DOCUMENTO: ", "")

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.amount is not None
    assert fields.amount.value == Decimal("1234.56")
    assert fields.amount.confidence == 0.9


def test_barcode_with_ocr_confusion_keeps_digits_and_lowers_confidence() -> None:
    boleto = build_boleto(include_barcode_text=True)
    confused = boleto.barcode.replace("0", "O", 1)
    text = boleto.ocr_text().replace(boleto.barcode, confused)

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.barcode is not None
    assert fields.barcode.value == boleto.barcode
    assert 0.5 <= fields.barcode.confidence < 0.95


def test_issue_date_is_not_used_as_due_date() -> None:
    boleto = build_boleto()
    assert boleto.due_date is not None
    text = boleto.ocr_text().replace(
        f"VENCIMENTO: {boleto.due_date.strftime('%d/%m/%Y')}",
        "EMISSAO: 01/01/2022",
    )

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.due_date is None


def test_unlabeled_date_has_low_confidence() -> None:
    boleto = build_boleto()
    assert boleto.due_date is not None
    text = boleto.ocr_text().replace(
        f"VENCIMENTO: {boleto.due_date.strftime('%d/%m/%Y')}",
        "01/01/2022",
    )

    fields = extract_boleto_fields(text, bank_directory=_directory())

    assert fields.due_date is not None
    assert fields.due_date.confidence == 0.45
