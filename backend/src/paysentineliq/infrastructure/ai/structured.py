import asyncio
import json
from typing import cast

from langchain_core.output_parsers import PydanticOutputParser

from paysentineliq.application.errors import LlmUnavailableError
from paysentineliq.application.ports.interpretation import (
    InterpretationRequest,
    InterpretationResult,
)
from paysentineliq.application.ports.llm import LlmMessage, LlmPort
from paysentineliq.infrastructure.ai.prompts import PromptRepository
from paysentineliq.infrastructure.ai.schemas import InterpretationOutput


class StructuredInterpreter:
    def __init__(
        self,
        llm: LlmPort,
        prompts: PromptRepository,
        *,
        max_attempts: int = 2,
        timeout_seconds: float = 30.0,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._llm = llm
        self._prompts = prompts
        self._max_attempts = max_attempts
        self._timeout = timeout_seconds
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._parser = PydanticOutputParser(pydantic_object=InterpretationOutput)

    async def interpret(
        self,
        request: InterpretationRequest,
    ) -> InterpretationResult:
        prompt = self._prompts.load(request.language)
        evidence = [
            {
                "rule": item.rule_id,
                "severity": item.severity,
                "weight": item.weight,
                "message_key": item.message_key,
            }
            for item in request.evidence
        ]
        rag_text = "\n\n".join(snippet[:1500] for snippet in request.rag_snippets[:5])
        messages = self._prompts.render(
            prompt,
            language=request.language,
            document_type=request.document_type,
            score=request.score,
            band=request.band,
            degradation_flags=",".join(request.degradation_flags) or "none",
            evidence_json=json.dumps(evidence, ensure_ascii=False),
            rag_text=rag_text or "sem trechos disponiveis",
            format_instructions=self._parser.get_format_instructions(),
        )

        for attempt in range(self._max_attempts):
            try:
                response = await asyncio.wait_for(
                    self._llm.complete(
                        messages,
                        temperature=self._temperature,
                        max_tokens=self._max_tokens,
                    ),
                    timeout=self._timeout,
                )
            except (TimeoutError, LlmUnavailableError) as exc:
                raise LlmUnavailableError("LLM is unavailable") from exc
            try:
                output = cast(
                    InterpretationOutput,
                    self._parser.parse(response.content),
                )
            except Exception as exc:
                if attempt + 1 >= self._max_attempts:
                    raise LlmUnavailableError(
                        "LLM did not return valid JSON",
                    ) from exc
                messages = (
                    *messages,
                    LlmMessage(role="assistant", content=response.content),
                    LlmMessage(
                        role="user",
                        content=(
                            "A resposta anterior nao e JSON valido para o esquema: "
                            f"{exc}. Responda apenas com JSON valido."
                        ),
                    ),
                )
                continue
            return InterpretationResult(
                justification=output.justification,
                inconsistencies=tuple(output.inconsistencies),
                model_version=self._llm.model,
                prompt_version=prompt.version,
            )
        raise LlmUnavailableError("LLM is unavailable")
