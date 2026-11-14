from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InterpretationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    justification: str = Field(min_length=1, max_length=2000)
    inconsistencies: list[str] = Field(default_factory=list)

    @field_validator("inconsistencies")
    @classmethod
    def _clean_inconsistencies(cls, values: list[str]) -> list[str]:
        cleaned = [" ".join(value.split())[:300] for value in values if value.strip()]
        return cleaned[:5]


class JudgeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    reason: Literal[
        "anchored",
        "not_anchored",
        "score_inconsistent",
        "instruction_leak",
        "unsafe_output",
        "other",
    ]
    findings: list[str] = Field(default_factory=list)

    @field_validator("findings")
    @classmethod
    def _clean_findings(cls, values: list[str]) -> list[str]:
        cleaned = [" ".join(value.split())[:300] for value in values if value.strip()]
        return cleaned[:5]
