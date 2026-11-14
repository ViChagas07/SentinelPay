import asyncio
import json
from typing import Protocol, cast

from langchain_core.output_parsers import PydanticOutputParser

from paysentineliq.application.errors import (
    GuardrailViolationError,
    LlmUnavailableError,
    SSRFBlockedError,
)
from paysentineliq.application.ports.interpretation import (
    InterpretationRequest,
    InterpretationResult,
)
from paysentineliq.application.security.guardrails import ToolAllowlist
from paysentineliq.application.security.redaction import escape_delimiters, mask_pii
from paysentineliq.infrastructure.ai.prompts import PromptRepository
from paysentineliq.infrastructure.ai.schemas import InterpretationOutput
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.security.ssrf import SSRFGuard


class CrewRunner(Protocol):
    async def run(
        self,
        *,
        system: str,
        user: str,
        prompt_version: str,
    ) -> InterpretationOutput: ...


class CrewAIInterpreter:
    def __init__(
        self,
        *,
        settings: Settings,
        prompts: PromptRepository,
        crew_runner: CrewRunner | None = None,
        guard: SSRFGuard | None = None,
        timeout_seconds: float = 60.0,
        max_document_chars: int = 20_000,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_document_chars <= 0:
            raise ValueError("max_document_chars must be positive")
        self._settings = settings
        self._prompts = prompts
        self._crew_runner = crew_runner
        self._guard = guard
        self._timeout = timeout_seconds
        self._max_document_chars = max_document_chars
        self._parser = PydanticOutputParser(pydantic_object=InterpretationOutput)

    async def interpret(
        self,
        request: InterpretationRequest,
    ) -> InterpretationResult:
        if ToolAllowlist().denied(request.tools):
            raise GuardrailViolationError()
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
        rag_text = escape_delimiters(
            "\n\n".join(snippet[:1500] for snippet in request.rag_snippets[:5]),
        )
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
            document_excerpt=escape_delimiters(mask_pii(request.document_excerpt))[
                : self._max_document_chars
            ],
        )
        system = messages[0].content
        user = messages[1].content
        if self._crew_runner is not None:
            output = await self._crew_runner.run(
                system=system,
                user=user,
                prompt_version=prompt.version,
            )
        else:
            output = await self._run_crew(system, user)
        return InterpretationResult(
            justification=output.justification,
            inconsistencies=tuple(output.inconsistencies),
            model_version=self._settings.llm_model,
            prompt_version=prompt.version,
        )

    async def _run_crew(self, system: str, user: str) -> InterpretationOutput:
        if (
            not self._settings.llm_base_url
            or not self._settings.llm_model
            or "CHANGE_ME" in self._settings.llm_model
        ):
            raise LlmUnavailableError("LLM is not configured")
        if self._guard is not None:
            try:
                await self._guard.validate_url(
                    f"{self._settings.llm_base_url.rstrip('/')}/chat/completions",
                    allow_internal=True,
                )
            except SSRFBlockedError as exc:
                raise LlmUnavailableError("LLM endpoint is blocked") from exc

        from crewai import LLM, Agent, Crew, Process, Task

        llm = LLM(
            model=self._settings.llm_model,
            base_url=self._settings.llm_base_url,
            api_key=self._settings.llm_api_key or None,
            temperature=self._settings.llm_temperature,
            timeout=self._settings.llm_timeout_seconds,
            max_tokens=self._settings.llm_max_output_tokens,
        )
        analyst = Agent(
            role="Analista de evidencias",
            goal="Identificar inconsistencias semanticas nas evidencias fornecidas.",
            backstory=(
                "Voce revisa evidencias deterministicas e trechos de conhecimento. "
                "Nao altera score e nao remove evidencias."
            ),
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )
        writer = Agent(
            role="Redator do relatorio",
            goal="Explicar o resultado em linguagem clara e devolver JSON valido.",
            backstory=(
                "Voce escreve explicacoes curtas, sem dados pessoais, usando apenas "
                "as evidencias e os trechos fornecidos."
            ),
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )
        analysis = Task(
            description=(
                f"{system}\n\n{user}\n\n"
                "Liste no maximo 5 inconsistencias semanticas curtas. "
                "Nao repita o score e nao invente dados."
            ),
            expected_output="Lista curta de inconsistencias semanticas.",
            agent=analyst,
        )
        report = Task(
            description=(
                f"{system}\n\n{user}\n\n"
                "Use as inconsistencias do analista e responda APENAS com JSON valido. "
                f"{self._parser.get_format_instructions()}"
            ),
            expected_output="JSON com justification e inconsistencies.",
            agent=writer,
            output_pydantic=InterpretationOutput,
            context=[analysis],
        )
        crew = Crew(
            agents=[analyst, writer],
            tasks=[analysis, report],
            process=Process.sequential,
            verbose=False,
            tracing=False,
        )
        result = await asyncio.wait_for(
            asyncio.to_thread(crew.kickoff),
            timeout=self._timeout,
        )
        output = getattr(result, "pydantic", None)
        if isinstance(output, InterpretationOutput):
            return output
        raw = getattr(result, "raw", None)
        if isinstance(raw, str):
            try:
                return cast(InterpretationOutput, self._parser.parse(raw))
            except Exception as exc:
                raise LlmUnavailableError(
                    "crew did not return valid structured output",
                ) from exc
        raise LlmUnavailableError("crew did not return structured output")
