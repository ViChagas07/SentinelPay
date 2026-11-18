from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from paysentineliq.application.ports.guardrails import JudgeRequest
from paysentineliq.application.ports.interpretation import (
    InterpretationEvidence,
    InterpretationRequest,
)
from paysentineliq.application.security.observability_masking import ObservabilityMasker
from paysentineliq.infrastructure.ai.crew import CrewAIInterpreter
from paysentineliq.infrastructure.ai.judge import LlmReportJudge
from paysentineliq.infrastructure.ai.prompts import PromptRepository
from paysentineliq.infrastructure.ai.schemas import InterpretationOutput
from paysentineliq.infrastructure.ai.structured import StructuredInterpreter
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.observability.langfuse_tracer import (
    LangfuseTracer,
    build_observability_tracer,
)
from paysentineliq.infrastructure.observability.noop_tracer import NoopTracer
from tests.support.llm_fakes import FakeLlm

pytestmark = pytest.mark.unit

_CPF = "529.982.247-25"
_CPF_PLAIN = "52998224725"
_MONEY = "R$ 1.234,56"
_LINE = "34191.79001 01043.510047 91020.150008 9 12345678901234"
_EMAIL = "joao@example.com"
_PHONE = "(11) 91234-5678"
_NAME = "João da Silva"
_PIX = "123e4567-e89b-12d3-a456-426614174000"
_PII = (
    f"Nome: {_NAME}, CPF {_CPF}, valor {_MONEY}, linha {_LINE}, "
    f"e-mail {_EMAIL}, telefone {_PHONE}, PIX {_PIX}"
)


def _assert_no_sensitive(payload: object) -> None:
    rendered = repr(payload)
    for raw in (
        _NAME,
        _CPF,
        _CPF_PLAIN,
        _MONEY,
        _LINE,
        _EMAIL,
        _PHONE,
        _PIX,
    ):
        assert raw not in rendered


class FakeSpan:
    def __init__(self, client: "FakeClient") -> None:
        self._client = client

    def update(self, **kwargs: Any) -> None:
        if self._client.fail_on_update:
            raise RuntimeError("langfuse update failed")
        _assert_no_sensitive(kwargs)
        self._client.updates.append(kwargs)


class FakeClient:
    def __init__(self) -> None:
        self.started: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []
        self.scores: list[dict[str, Any]] = []
        self.flushes = 0
        self.shutdowns = 0
        self.fail_on_update = False

    @contextmanager
    def start_as_current_observation(
        self,
        *,
        name: str,
        as_type: str = "generation",
        input: Any = None,
        metadata: Any = None,
        model: str | None = None,
    ) -> Iterator[FakeSpan]:
        payload = {
            "name": name,
            "as_type": as_type,
            "input": input,
            "metadata": metadata,
            "model": model,
        }
        _assert_no_sensitive(payload)
        self.started.append(payload)
        yield FakeSpan(self)

    def score_current_trace(
        self,
        *,
        name: str,
        value: float | str,
        data_type: str | None = None,
        comment: str | None = None,
    ) -> None:
        payload = {
            "name": name,
            "value": value,
            "data_type": data_type,
            "comment": comment,
        }
        _assert_no_sensitive(payload)
        self.scores.append(payload)

    def get_current_trace_id(self) -> str | None:
        return "trace-test"

    def flush(self) -> None:
        self.flushes += 1

    def shutdown(self) -> None:
        self.shutdowns += 1


class RaisingClient:
    def start_as_current_observation(
        self,
        *,
        name: str,
        as_type: str = "generation",
        input: Any = None,
        metadata: Any = None,
        model: str | None = None,
    ) -> Any:
        raise RuntimeError("langfuse start failed")

    def score_current_trace(
        self,
        *,
        name: str,
        value: float | str,
        data_type: str | None = None,
        comment: str | None = None,
    ) -> None:
        raise RuntimeError("langfuse score failed")

    def get_current_trace_id(self) -> str | None:
        raise RuntimeError("langfuse trace id failed")

    def flush(self) -> None:
        raise RuntimeError("langfuse flush failed")

    def shutdown(self) -> None:
        raise RuntimeError("langfuse shutdown failed")


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
        document_excerpt=_PII,
    )


def test_masks_all_payloads_before_sending_to_client() -> None:
    client = FakeClient()
    tracer = LangfuseTracer(client, ObservabilityMasker(hash_secret="test-secret"))

    with tracer.observation(
        "llm.interpret",
        input={"document_excerpt": _PII, "user_id": "user-123"},
        metadata={"payer_name": _NAME, "amount": _MONEY},
        model="qwen",
    ) as handle:
        handle.update(
            output={"justification": _PII, "inconsistencies": [_PII]},
            metadata={"outcome": "success"},
        )

    assert client.started
    assert client.updates
    assert client.started[0]["input"]["user_id"].startswith("sha256:")
    assert client.started[0]["input"]["document_excerpt"]["sha256"]
    assert client.started[0]["metadata"]["payer_name"] == "[REDACTED_NAME]"
    assert client.started[0]["metadata"]["amount"] == "[REDACTED_MONEY]"


async def test_flush_and_shutdown_delegate_to_client() -> None:
    client = FakeClient()
    tracer = LangfuseTracer(client, ObservabilityMasker())

    await tracer.flush()
    await tracer.aclose()

    assert client.flushes == 1
    assert client.shutdowns == 1


async def test_failures_never_escape_the_tracer() -> None:
    tracer = LangfuseTracer(RaisingClient(), ObservabilityMasker())

    with tracer.observation("llm.interpret", input={"content": _PII}) as handle:
        handle.update(output={"content": _PII})
    await tracer.flush()
    await tracer.aclose()


async def test_update_failure_never_breaks_the_pipeline() -> None:
    client = FakeClient()
    client.fail_on_update = True
    tracer = LangfuseTracer(client, ObservabilityMasker())

    with tracer.observation("llm.interpret") as handle:
        handle.update(output={"content": _PII})


async def test_structured_interpreter_sends_only_masked_payloads() -> None:
    client = FakeClient()
    tracer = LangfuseTracer(client, ObservabilityMasker(hash_secret="test-secret"))
    llm = FakeLlm(
        [
            '{"justification": "CPF 529.982.247-25 e valor R$ 1.234,56", '
            '"inconsistencies": ["Nome: João da Silva"]}',
        ],
    )
    interpreter = StructuredInterpreter(
        llm,
        PromptRepository(),
        tracer=tracer,
    )

    result = await interpreter.interpret(_request())

    assert result.justification
    assert client.started[0]["name"] == "llm.interpret"
    assert client.started[0]["input"]["document_excerpt"]["sha256"]
    assert client.updates[0]["output"]["justification"]["sha256"]


async def test_noop_tracer_does_not_change_pipeline_result() -> None:
    without_tracer = StructuredInterpreter(
        FakeLlm(['{"justification": "ok", "inconsistencies": []}']),
        PromptRepository(),
    )
    with_noop = StructuredInterpreter(
        FakeLlm(['{"justification": "ok", "inconsistencies": []}']),
        PromptRepository(),
        tracer=NoopTracer(),
    )

    first = await without_tracer.interpret(_request())
    second = await with_noop.interpret(_request())

    assert first == second


def test_factory_uses_noop_when_disabled_or_without_keys() -> None:
    assert isinstance(
        build_observability_tracer(Settings(app_env="local")),
        NoopTracer,
    )
    assert isinstance(
        build_observability_tracer(
            Settings(app_env="local", langfuse_enabled=True),
        ),
        NoopTracer,
    )


def test_factory_builds_langfuse_tracer_with_expected_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    client = FakeClient()

    class FakeLangfuse:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        def start_as_current_observation(
            self,
            **kwargs: Any,
        ) -> Any:
            return client.start_as_current_observation(**kwargs)

        def flush(self) -> None:
            client.flush()

        def shutdown(self) -> None:
            client.shutdown()

    monkeypatch.setattr("langfuse.Langfuse", FakeLangfuse)
    settings = Settings(
        app_env="local",
        langfuse_enabled=True,
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
        langfuse_host="https://langfuse.example",
        langfuse_sample_rate=0.25,
    )

    tracer = build_observability_tracer(settings)

    assert isinstance(tracer, LangfuseTracer)
    assert captured["public_key"] == "pk-test"
    assert captured["secret_key"] == "sk-test"
    assert captured["base_url"] == "https://langfuse.example"
    assert captured["sample_rate"] == 0.25
    assert captured["timeout"] == 2
    assert captured["flush_at"] == 10
    assert captured["flush_interval"] == 2.0
    assert captured["mask"] is not None


class FakeCrewRunner:
    def __init__(self, output: InterpretationOutput) -> None:
        self._output = output

    async def run(
        self,
        *,
        system: str,
        user: str,
        prompt_version: str,
    ) -> InterpretationOutput:
        return self._output


async def test_crew_interpreter_traces_masked_output() -> None:
    client = FakeClient()
    tracer = LangfuseTracer(client, ObservabilityMasker(hash_secret="test-secret"))
    runner = FakeCrewRunner(
        InterpretationOutput(
            justification="CPF 529.982.247-25 e valor R$ 1.234,56",
            inconsistencies=["Nome: Jo\u00e3o da Silva"],
        ),
    )
    settings = Settings(
        app_env="local",
        jwt_secret="s" * 64,
        security_hash_secret="h" * 32,
        llm_base_url="http://localhost:1234/v1",
        llm_model="fake-model",
    )
    interpreter = CrewAIInterpreter(
        settings=settings,
        prompts=PromptRepository(),
        crew_runner=runner,
        tracer=tracer,
    )

    await interpreter.interpret(_request())

    assert client.started[0]["name"] == "llm.crew_interpret"
    assert client.updates[0]["output"]["justification"]["sha256"]

    judge_llm = FakeLlm(
        [
            '{"approved": true, "reason": "anchored", '
            '"findings": ["CPF 529.982.247-25", "valor R$ 1.234,56"]}',
        ],
    )
    judge = LlmReportJudge(judge_llm, PromptRepository(), tracer=tracer)
    await judge.judge(
        JudgeRequest(
            document_type="boleto",
            score=42,
            band="attention",
            justification="CPF 529.982.247-25",
            inconsistencies=("Nome: Jo\u00e3o da Silva",),
            evidence=(
                InterpretationEvidence(
                    rule_id="dv_invalid",
                    severity="critical",
                    weight=70,
                    message_key="boleto.dv_invalid",
                ),
            ),
            language="pt",
        ),
    )

    assert client.started[1]["name"] == "llm.judge"
    assert client.updates[1]["output"]["verdict_reason"] == "anchored"
    assert client.updates[1]["output"]["findings"][0]["sha256"]


class EnterFailingManager:
    def __enter__(self) -> Any:
        raise RuntimeError("langfuse enter failed")

    def __exit__(self, *args: Any) -> None:
        return None


class EnterFailingClient:
    def start_as_current_observation(
        self,
        *,
        name: str,
        as_type: str = "generation",
        input: Any = None,
        metadata: Any = None,
        model: str | None = None,
    ) -> EnterFailingManager:
        return EnterFailingManager()

    def score_current_trace(
        self,
        *,
        name: str,
        value: float | str,
        data_type: str | None = None,
        comment: str | None = None,
    ) -> None:
        return None

    def get_current_trace_id(self) -> str | None:
        return None

    def flush(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


async def test_enter_failure_falls_back_to_noop_without_raising() -> None:
    tracer = LangfuseTracer(EnterFailingClient(), ObservabilityMasker())

    with tracer.observation("llm.interpret", input={"content": _PII}) as handle:
        handle.update(output={"content": _PII})
    await tracer.flush()
    await tracer.aclose()


@contextmanager
def _capture_propagate(
    captured: list[dict[str, Any]],
    kwargs: dict[str, Any],
) -> Iterator[None]:
    captured.append(kwargs)
    yield


def test_trace_sets_session_tags_environment_and_masks() -> None:
    client = FakeClient()
    captured: list[dict[str, Any]] = []
    tracer = LangfuseTracer(
        client,
        ObservabilityMasker(hash_secret="test-secret"),
        propagate=lambda **kwargs: _capture_propagate(captured, kwargs),
    )

    with tracer.trace(
        "analysis",
        session_id="analysis-1",
        metadata={"user_id": "user-123", "document_excerpt": _PII},
        tags=("analysis", "env:local"),
        environment="local",
        input={"document_excerpt": _PII},
    ) as handle:
        handle.update(output={"justification": _PII})

    assert captured[0]["session_id"] == "analysis-1"
    assert captured[0]["tags"] == ["analysis", "env:local"]
    assert captured[0]["environment"] == "local"
    assert captured[0]["trace_name"] == "analysis"
    assert client.started[0]["name"] == "analysis"
    assert client.started[0]["metadata"]["user_id"].startswith("sha256:")
    assert isinstance(client.started[0]["input"]["document_excerpt"], dict)
    assert isinstance(client.updates[0]["output"]["justification"], dict)


def test_scores_are_masked_and_forwarded() -> None:
    client = FakeClient()
    tracer = LangfuseTracer(client, ObservabilityMasker(hash_secret="test-secret"))

    tracer.score(
        "judge_verdict",
        _PII,
        data_type="CATEGORICAL",
        comment=_PII,
    )

    assert client.scores[0]["name"] == "judge_verdict"
    assert client.scores[0]["data_type"] == "CATEGORICAL"
    _assert_no_sensitive(client.scores[0])


async def test_current_trace_id_is_exposed_and_failures_are_safe() -> None:
    tracer = LangfuseTracer(FakeClient(), ObservabilityMasker())
    failing = LangfuseTracer(RaisingClient(), ObservabilityMasker())

    assert tracer.current_trace_id() == "trace-test"
    assert failing.current_trace_id() is None
    failing.score("risk_score", 42.0, data_type="NUMERIC")
    await failing.flush()
    await failing.aclose()


def test_noop_tracer_exposes_trace_score_and_trace_id_without_side_effects() -> None:
    tracer = NoopTracer()

    with tracer.trace("analysis", session_id="analysis-1") as handle:
        handle.update(output={"content": _PII})
    tracer.score("risk_score", 42.0, data_type="NUMERIC")

    assert tracer.current_trace_id() is None
