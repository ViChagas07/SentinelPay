import os

import httpx
import pytest

from paysentineliq.application.ports.interpretation import (
    InterpretationEvidence,
    InterpretationRequest,
)
from paysentineliq.infrastructure.ai.llm import OpenAICompatibleLLM
from paysentineliq.infrastructure.ai.prompts import PromptRepository
from paysentineliq.infrastructure.ai.structured import StructuredInterpreter
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.security.ssrf import SafeHttpClient, SSRFGuard

pytestmark = pytest.mark.manual

_SKIP = (
    os.environ.get("RUN_REAL_LLM") != "1"
    or not os.environ.get("LLM_MODEL")
    or "CHANGE_ME" in os.environ.get("LLM_MODEL", "")
)


@pytest.mark.skipif(_SKIP, reason="set RUN_REAL_LLM=1 and LLM_MODEL for LM Studio")
async def test_real_llm_returns_structured_interpretation() -> None:
    settings = Settings()
    guard = SSRFGuard(
        require_https=False,
        allowed_hosts=set(settings.ssrf_allowed_hosts_list),
    )
    client = SafeHttpClient(
        guard,
        timeout=httpx.Timeout(settings.llm_timeout_seconds),
    )
    llm = OpenAICompatibleLLM(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        temperature=settings.llm_temperature,
        max_retries=settings.llm_max_retries,
        backoff_seconds=settings.embedding_retry_backoff_seconds,
        client=client,
    )
    interpreter = StructuredInterpreter(
        llm,
        PromptRepository(),
        timeout_seconds=settings.llm_timeout_seconds,
    )

    result = await interpreter.interpret(
        InterpretationRequest(
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
        ),
    )

    assert result.justification
    assert len(result.inconsistencies) <= 5
    assert result.model_version == settings.llm_model
