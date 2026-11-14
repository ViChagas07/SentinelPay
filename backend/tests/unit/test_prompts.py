import pytest

from paysentineliq.infrastructure.ai.prompts import PromptRepository

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("locale", ["pt-BR", "pt", "es", "en"])
def test_prompts_load_and_are_versioned(locale: str) -> None:
    prompt = PromptRepository().load(locale)

    assert prompt.system
    assert prompt.user
    assert prompt.version.startswith("p12-")
    assert "{evidence_json}" in prompt.user
    assert "{rag_text}" in prompt.user


def test_unknown_locale_falls_back_to_portuguese() -> None:
    repository = PromptRepository()

    assert repository.load("fr").version == repository.load("pt").version


def test_render_produces_system_and_user_messages() -> None:
    repository = PromptRepository()
    prompt = repository.load("en")

    messages = repository.render(
        prompt,
        language="en",
        document_type="boleto",
        score=42,
        band="attention",
        degradation_flags="ml_unavailable",
        evidence_json='[{"rule": "dv_invalid"}]',
        rag_text="Trecho de teste",
        format_instructions='{"justification": "text"}',
    )

    assert [message.role for message in messages] == ["system", "user"]
    assert "dv_invalid" in messages[1].content
    assert "Trecho de teste" in messages[1].content
    assert "attention" in messages[1].content
