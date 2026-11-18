import pytest

from paysentineliq.application.security.observability_masking import (
    ObservabilityMasker,
)

pytestmark = pytest.mark.unit

_PII = (
    "Nome: João da Silva, CPF 529.982.247-25, CNPJ 11.222.333/0001-81, "
    "valor R$ 1.234,56, linha 34191.79001 01043.510047 91020.150008 9 12345678901234, "
    "e-mail joao@example.com, telefone (11) 91234-5678, "
    "PIX 123e4567-e89b-12d3-a456-426614174000, CEP 01310-100, "
    "Endereço: Avenida Paulista, 1000"
)


def _masker() -> ObservabilityMasker:
    return ObservabilityMasker(hash_secret="test-secret")


def test_masks_cpf_and_cnpj_formatted_and_unformatted() -> None:
    masker = _masker()

    assert "529.982.247-25" not in masker.mask_text("CPF 529.982.247-25")
    assert "52998224725" not in masker.mask_text("CPF 52998224725")
    assert "529 982 247 25" not in masker.mask_text("CPF 529 982 247 25")
    assert "11.222.333/0001-81" not in masker.mask_text("CNPJ 11.222.333/0001-81")
    assert "11222333000181" not in masker.mask_text("CNPJ 11222333000181")
    assert "[REDACTED_CPF]" in masker.mask_text("CPF 52998224725")
    assert "[REDACTED_CNPJ]" in masker.mask_text("CNPJ 11222333000181")


def test_masks_money_digitable_line_and_barcode() -> None:
    masker = _masker()

    assert "1.234,56" not in masker.mask_text("valor R$ 1.234,56")
    assert "[REDACTED_MONEY]" in masker.mask_text("total 2.500,00")
    assert "34191.79001" not in masker.mask_text(
        "linha 34191.79001 01043.510047 91020.150008 9 12345678901234",
    )
    barcode = "1" * 44
    assert barcode not in masker.mask_text(f"codigo {barcode}")
    assert "[REDACTED_LINE]" in masker.mask_text(f"codigo {barcode}")


def test_masks_email_phone_and_pix_key() -> None:
    masker = _masker()

    assert "joao@example.com" not in masker.mask_text("email joao@example.com")
    assert "91234-5678" not in masker.mask_text("telefone (11) 91234-5678")
    assert "612 345 678" not in masker.mask_text("telefono +34 612 345 678")
    assert "123e4567-e89b-12d3-a456-426614174000" not in masker.mask_text(
        "PIX: 123e4567-e89b-12d3-a456-426614174000",
    )
    assert "[REDACTED_EMAIL]" in masker.mask_text("email joao@example.com")
    assert "[REDACTED_PHONE]" in masker.mask_text("telefone (11) 91234-5678")
    assert "[REDACTED_PIX_KEY]" in masker.mask_text(
        "PIX: 123e4567-e89b-12d3-a456-426614174000",
    )


def test_masks_names_in_portuguese_spanish_and_english() -> None:
    masker = _masker()

    pt = masker.mask_text("Nome: João da Silva")
    es = masker.mask_text("Nombre: Juan Pérez")
    en = masker.mask_text("Name: John Smith")

    assert "João" not in pt
    assert "Juan" not in es
    assert "John" not in en
    assert "[REDACTED_NAME]" in pt
    assert "[REDACTED_NAME]" in es
    assert "[REDACTED_NAME]" in en


def test_masks_address_and_cep() -> None:
    masker = _masker()

    assert "Avenida Paulista" not in masker.mask_text("Endereço: Avenida Paulista, 1000")
    assert "Calle Mayor" not in masker.mask_text("dirección: Calle Mayor 10")
    assert "123 Main Street" not in masker.mask_text("address: 123 Main Street")
    assert "01310-100" not in masker.mask_text("CEP 01310-100")


def test_masks_full_text_without_leaking_any_example() -> None:
    masked = _masker().mask_text(_PII)

    for raw in (
        "João da Silva",
        "529.982.247-25",
        "11.222.333/0001-81",
        "1.234,56",
        "34191.79001",
        "joao@example.com",
        "91234-5678",
        "123e4567-e89b-12d3-a456-426614174000",
        "01310-100",
        "Avenida Paulista",
    ):
        assert raw not in masked


def test_masks_structured_payload_and_hashes_identifiers() -> None:
    masker = _masker()
    payload = {
        "user_id": "user-123",
        "analysis_id": "123e4567-e89b-12d3-a456-426614174000",
        "payer_name": "João da Silva",
        "amount": 1234.56,
        "digitable_line": "34191.79001 01043.510047 91020.150008 9 12345678901234",
        "document_excerpt": _PII,
        "justification": "Nome: João, valor R$ 10,00",
        "metadata": {
            "email": "joao@example.com",
            "score": 42,
            "model": "qwen",
        },
    }

    masked = masker.mask_payload(payload)

    assert masked["user_id"].startswith("sha256:")
    assert "user-123" not in masked["user_id"]
    assert masked["analysis_id"] == payload["analysis_id"]
    assert masked["payer_name"] == "[REDACTED_NAME]"
    assert masked["amount"] == "[REDACTED_MONEY]"
    assert masked["digitable_line"] == "[REDACTED_LINE]"
    assert isinstance(masked["document_excerpt"], dict)
    assert "sha256" in masked["document_excerpt"]
    assert isinstance(masked["justification"], dict)
    assert masked["metadata"]["email"] == "[REDACTED_EMAIL]"
    assert masked["metadata"]["score"] == 42
    assert masked["metadata"]["model"] == "qwen"


def test_hash_identifier_is_deterministic_and_secret_dependent() -> None:
    first = ObservabilityMasker(hash_secret="one").hash_identifier("user-123")
    again = ObservabilityMasker(hash_secret="one").hash_identifier("user-123")
    other = ObservabilityMasker(hash_secret="two").hash_identifier("user-123")

    assert first == again
    assert first != other
    assert "user-123" not in first
