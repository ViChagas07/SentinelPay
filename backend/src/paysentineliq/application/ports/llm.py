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

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("content is required")
        if not self.model.strip():
            raise ValueError("model is required")


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
