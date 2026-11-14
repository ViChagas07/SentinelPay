import pytest

from paysentineliq.application.errors import LlmUnavailableError
from paysentineliq.application.ports.interpretation import (
    InterpretationEvidence,
    InterpretationRequest,
)
from paysentineliq.infrastructure.ai.prompts import PromptRepository
from paysentineliq.infrastructure.ai.structured import StructuredInterpreter
from tests.support.llm_fakes import FakeLlm, SlowLlm

pytestmark = pytest.mark.unit

_VALID = '{"justification": "Explicacao objetiva.", "inconsistencies": ["sugestao"]}'


def _request(language: str = "pt") -> InterpretationRequest:
    return InterpretationRequest(
        document_type="boleto",
        score=42,
        band="attention",
        evidence=(
            InterpretationEvidence(
                rule_id="dv_invalid",
                severity="critical",
                weight=70,
                message_key="boleto.dv_invalid",
            ),
        ),
        rag_snippets=("Trecho de conhecimento.",),
        language=language,
    )


async def test_valid_json_is_parsed() -> None:
    llm = FakeLlm([_VALID])
    interpreter = StructuredInterpreter(llm, PromptRepository())

    result = await interpreter.interpret(_request())

    assert result.justification == "Explicacao objetiva."
    assert result.inconsistencies == ("sugestao",)
    assert result.model_version == "fake-llm"
    assert result.prompt_version.startswith("p11-")
    assert llm.calls == 1


async def test_invalid_json_is_repaired_once() -> None:
    llm = FakeLlm(["not json", _VALID])
    interpreter = StructuredInterpreter(llm, PromptRepository(), max_attempts=2)

    result = await interpreter.interpret(_request("es"))

    assert result.justification == "Explicacao objetiva."
    assert llm.calls == 2
    assert llm.last_messages[-1].role == "user"
    assert "JSON" in llm.last_messages[-1].content


async def test_invalid_json_exhausts_attempts() -> None:
    llm = FakeLlm(["not json", "still not json"])
    interpreter = StructuredInterpreter(llm, PromptRepository(), max_attempts=2)

    with pytest.raises(LlmUnavailableError):
        await interpreter.interpret(_request())


async def test_timeout_is_reported_as_unavailable() -> None:
    interpreter = StructuredInterpreter(
        SlowLlm(),
        PromptRepository(),
        timeout_seconds=0.01,
    )

    with pytest.raises(LlmUnavailableError):
        await interpreter.interpret(_request())


async def test_inconsistencies_are_capped_at_five() -> None:
    llm = FakeLlm(
        [
            '{"justification": "ok", "inconsistencies": ["1","2","3","4","5","6"]}',
        ],
    )
    interpreter = StructuredInterpreter(llm, PromptRepository())

    result = await interpreter.interpret(_request())

    assert len(result.inconsistencies) == 5
