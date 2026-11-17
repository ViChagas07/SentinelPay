import pytest

from paysentineliq.infrastructure.rag.text_cleanup import repair_text

pytestmark = pytest.mark.unit


def test_repair_text_fixes_double_encoded_utf8() -> None:
    assert repair_text("dÃ­gitos") == "dígitos"
    assert repair_text("RegulaÃ§Ã£o") == "Regulação"
    assert repair_text("NÃƒO") == "NÃO"


def test_repair_text_preserves_correct_latin1_text() -> None:
    assert repair_text("Regulação e dígitos") == "Regulação e dígitos"


def test_repair_text_normalizes_unicode_and_dashes() -> None:
    assert repair_text("Validac\u0327a\u0303o") == "Validação"
    assert repair_text("Linha Digitável — Estrutura") == "Linha Digitável, Estrutura"
    assert repair_text("Razão \u2013 social") == "Razão - social"
    assert repair_text("A\u00a0B") == "A B"


def test_repair_text_is_idempotent() -> None:
    original = "RegulaÃ§Ã£o — banco"
    once = repair_text(original)

    assert repair_text(once) == once
    assert once == "Regulação, banco"
