from dataclasses import dataclass
from typing import Protocol

from paysentineliq.application.ports.interpretation import InterpretationEvidence


class GuardrailMetricsPort(Protocol):
    def record(self, layer: str, code: str) -> None: ...


class InjectionClassifierPort(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def model_version(self) -> str: ...

    def score(self, text: str) -> float: ...


@dataclass(frozen=True, slots=True)
class JudgeRequest:
    document_type: str
    score: int
    band: str
    justification: str
    inconsistencies: tuple[str, ...]
    evidence: tuple[InterpretationEvidence, ...]
    language: str = "pt"

    def __post_init__(self) -> None:
        if not self.document_type.strip():
            raise ValueError("document_type is required")
        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")
        if not self.band.strip():
            raise ValueError("band is required")
        if not self.justification.strip():
            raise ValueError("justification is required")


@dataclass(frozen=True, slots=True)
class JudgeVerdict:
    approved: bool
    reason: str
    findings: tuple[str, ...]
    model_version: str
    prompt_version: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("reason is required")
        if len(self.findings) > 5:
            raise ValueError("at most five findings are allowed")
        if not self.model_version.strip() or not self.prompt_version.strip():
            raise ValueError("model and prompt versions are required")


class ReportJudgePort(Protocol):
    async def judge(self, request: JudgeRequest) -> JudgeVerdict: ...
