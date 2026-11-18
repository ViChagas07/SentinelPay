from dataclasses import dataclass
from typing import Literal, Protocol

LlmRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class LlmMessage:
    role: LlmRole
    content: str


@dataclass(frozen=True, slots=True)
class LlmResponse:
    content: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("content is required")
        if not self.model.strip():
            raise ValueError("model is required")
        for value in (self.prompt_tokens, self.completion_tokens, self.total_tokens):
            if value is not None and value < 0:
                raise ValueError("token counts must be non-negative")


class LlmPort(Protocol):
    @property
    def model(self) -> str: ...

    async def complete(
        self,
        messages: tuple[LlmMessage, ...],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> LlmResponse: ...
