from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class InterpretationEvidence:
    rule_id: str
    severity: str
    weight: int
    message_key: str


@dataclass(frozen=True, slots=True)
class InterpretationRequest:
    document_type: str
    score: int
    band: str
    evidence: tuple[InterpretationEvidence, ...]
    rag_snippets: tuple[str, ...]
    language: str = "pt"
    degradation_flags: tuple[str, ...] = ()
    document_excerpt: str = ""
    tools: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.document_type.strip():
            raise ValueError("document_type is required")
        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")
        if not self.band.strip():
            raise ValueError("band is required")


@dataclass(frozen=True, slots=True)
class InterpretationResult:
    justification: str
    inconsistencies: tuple[str, ...]
    model_version: str
    prompt_version: str

    def __post_init__(self) -> None:
        if not self.justification.strip():
            raise ValueError("justification is required")
        if len(self.inconsistencies) > 5:
            raise ValueError("at most five inconsistencies are allowed")
        if not self.model_version.strip() or not self.prompt_version.strip():
            raise ValueError("model and prompt versions are required")


class EvidenceInterpreterPort(Protocol):
    async def interpret(
        self,
        request: InterpretationRequest,
    ) -> InterpretationResult: ...
