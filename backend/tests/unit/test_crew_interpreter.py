import pytest

from paysentineliq.application.errors import LlmUnavailableError
from paysentineliq.application.ports.interpretation import (
    InterpretationEvidence,
    InterpretationRequest,
)
from paysentineliq.infrastructure.ai.crew import CrewAIInterpreter
from paysentineliq.infrastructure.ai.prompts import PromptRepository
from paysentineliq.infrastructure.ai.schemas import InterpretationOutput
from paysentineliq.infrastructure.config import Settings

pytestmark = pytest.mark.unit


class FakeCrewRunner:
    def __init__(
        self,
        *,
        output: InterpretationOutput | None = None,
        error: Exception | None = None,
    ) -> None:
        self._output = output
        self._error = error
        self.calls: list[dict[str, str]] = []

    async def run(
        self,
        *,
        system: str,
        user: str,
        prompt_version: str,
    ) -> InterpretationOutput:
        self.calls.append(
            {"system": system, "user": user, "prompt_version": prompt_version},
        )
        if self._error is not None:
            raise self._error
        if self._output is None:
            raise RuntimeError("no output configured")
        return self._output


def _settings(*, model: str = "fake-model") -> Settings:
    return Settings(
        app_env="local",
        jwt_secret="s" * 64,
        security_hash_secret="h" * 32,
        llm_base_url="http://localhost:1234/v1",
        llm_model=model,
    )


def _request() -> InterpretationRequest:
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
        language="pt",
    )


async def test_crew_interpreter_returns_structured_result() -> None:
    runner = FakeCrewRunner(
        output=InterpretationOutput(
            justification="Justificativa da crew.",
            inconsistencies=["Inconsistencia sugerida."],
        ),
    )
    interpreter = CrewAIInterpreter(
        settings=_settings(),
        prompts=PromptRepository(),
        crew_runner=runner,
    )

    result = await interpreter.interpret(_request())

    assert result.justification == "Justificativa da crew."
    assert result.inconsistencies == ("Inconsistencia sugerida.",)
    assert result.model_version == "fake-model"
    assert result.prompt_version.startswith("p12-")
    assert len(runner.calls) == 1
    assert "dv_invalid" in runner.calls[0]["user"]
    assert "Trecho de conhecimento." in runner.calls[0]["user"]


async def test_crew_runner_error_propagates() -> None:
    interpreter = CrewAIInterpreter(
        settings=_settings(),
        prompts=PromptRepository(),
        crew_runner=FakeCrewRunner(error=LlmUnavailableError("offline")),
    )

    with pytest.raises(LlmUnavailableError):
        await interpreter.interpret(_request())


async def test_missing_llm_configuration_raises_without_call() -> None:
    interpreter = CrewAIInterpreter(
        settings=_settings(model=""),
        prompts=PromptRepository(),
    )

    with pytest.raises(LlmUnavailableError):
        await interpreter.interpret(_request())
