from pydantic import BaseModel, Field, field_validator


class InterpretationOutput(BaseModel):
    justification: str = Field(min_length=1, max_length=2000)
    inconsistencies: list[str] = Field(default_factory=list)

    @field_validator("inconsistencies")
    @classmethod
    def _clean_inconsistencies(cls, values: list[str]) -> list[str]:
        cleaned = [" ".join(value.split())[:300] for value in values if value.strip()]
        return cleaned[:5]
