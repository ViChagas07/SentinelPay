import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from paysentineliq.application.ports.llm import LlmMessage, LlmRole

_DEFAULT_ROOT = Path(__file__).with_name("prompts")
_SECTION_RE = re.compile(r"#\s*SYSTEM\s*(.*?)\s*#\s*USER\s*(.*)", re.DOTALL | re.IGNORECASE)
_ROLE_MAP: dict[str, LlmRole] = {
    "system": "system",
    "human": "user",
    "ai": "assistant",
}


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    system: str
    user: str
    version: str


class PromptRepository:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root if root is not None else _DEFAULT_ROOT

    @staticmethod
    def _language(locale: str) -> str:
        language = locale.lower().split("-", 1)[0]
        return language if language in ("pt", "es", "en") else "pt"

    def load(self, locale: str) -> PromptTemplate:
        return self._load(f"{self._language(locale)}.md", prefix="p12")

    def load_judge(self, locale: str) -> PromptTemplate:
        return self._load(f"judge_{self._language(locale)}.md", prefix="p12-judge")

    def _load(self, filename: str, *, prefix: str) -> PromptTemplate:
        path = self._root / filename
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        match = _SECTION_RE.search(text)
        if match is None:
            raise ValueError(f"prompt file {path.name} has no SYSTEM/USER sections")
        version = f"{prefix}-{hashlib.sha256(raw).hexdigest()[:16]}"
        return PromptTemplate(
            system=match.group(1).strip(),
            user=match.group(2).strip(),
            version=version,
        )

    def render(
        self,
        prompt: PromptTemplate,
        *,
        language: str,
        document_type: str,
        score: int,
        band: str,
        degradation_flags: str,
        evidence_json: str,
        rag_text: str,
        format_instructions: str,
        document_excerpt: str = "",
    ) -> tuple[LlmMessage, ...]:
        return self._render(
            prompt,
            {
                "language": language,
                "document_type": document_type,
                "score": score,
                "band": band,
                "degradation_flags": degradation_flags,
                "evidence_json": evidence_json,
                "rag_text": rag_text,
                "format_instructions": format_instructions,
                "document_excerpt": document_excerpt,
            },
        )

    def render_judge(
        self,
        prompt: PromptTemplate,
        *,
        language: str,
        document_type: str,
        score: int,
        band: str,
        evidence_json: str,
        justification: str,
        inconsistencies_json: str,
        format_instructions: str,
    ) -> tuple[LlmMessage, ...]:
        return self._render(
            prompt,
            {
                "language": language,
                "document_type": document_type,
                "score": score,
                "band": band,
                "evidence_json": evidence_json,
                "justification": justification,
                "inconsistencies_json": inconsistencies_json,
                "format_instructions": format_instructions,
            },
        )

    def _render(
        self,
        prompt: PromptTemplate,
        values: dict[str, Any],
    ) -> tuple[LlmMessage, ...]:
        template = ChatPromptTemplate.from_messages(
            [("system", prompt.system), ("human", prompt.user)],
        )
        messages = template.format_messages(**values)
        return tuple(
            LlmMessage(
                role=_ROLE_MAP.get(message.type, "system"),
                content=(
                    message.content if isinstance(message.content, str) else str(message.content)
                ),
            )
            for message in messages
        )
