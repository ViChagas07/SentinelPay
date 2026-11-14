import asyncio
import json
from typing import cast

from langchain_core.output_parsers import PydanticOutputParser

from paysentineliq.application.errors import LlmUnavailableError
from paysentineliq.application.ports.guardrails import (
    JudgeRequest,
    JudgeVerdict,
)
from paysentineliq.application.ports.llm import LlmPort
from paysentineliq.application.security.redaction import escape_delimiters
from paysentineliq.infrastructure.ai.prompts import PromptRepository
from paysentineliq.infrastructure.ai.schemas import JudgeOutput


class LlmReportJudge:
    def __init__(
        self,
        llm: LlmPort,
        prompts: PromptRepository,
        *,
        timeout_seconds: float = 30.0,
        temperature: float = 0.0,
        max_tokens: int = 500,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("temperature must be between 0 and 1")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        self._llm = llm
        self._prompts = prompts
        self._timeout = timeout_seconds
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._parser = PydanticOutputParser(pydantic_object=JudgeOutput)

    async def judge(self, request: JudgeRequest) -> JudgeVerdict:
        prompt = self._prompts.load_judge(request.language)
        evidence = [
            {
                "rule": item.rule_id,
                "severity": item.severity,
                "weight": item.weight,
                "message_key": item.message_key,
            }
            for item in request.evidence
        ]
        messages = self._prompts.render_judge(
            prompt,
            language=request.language,
            document_type=request.document_type,
            score=request.score,
            band=request.band,
            evidence_json=json.dumps(evidence, ensure_ascii=False),
            justification=escape_delimiters(request.justification),
            inconsistencies_json=escape_delimiters(
                json.dumps(
                    list(request.inconsistencies),
                    ensure_ascii=False,
                ),
            ),
            format_instructions=self._parser.get_format_instructions(),
        )
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
            raise LlmUnavailableError("judge is unavailable") from exc
        try:
            output = cast(JudgeOutput, self._parser.parse(response.content))
        except Exception as exc:
            raise LlmUnavailableError("judge did not return valid JSON") from exc
        return JudgeVerdict(
            approved=output.approved,
            reason=output.reason,
            findings=tuple(output.findings),
            model_version=self._llm.model,
            prompt_version=prompt.version,
        )
