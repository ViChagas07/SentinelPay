import asyncio

from paysentineliq.application.ports.llm import LlmMessage, LlmResponse


class FakeLlm:
    def __init__(
        self,
        responses: list[str | Exception],
        *,
        model: str = "fake-llm",
    ) -> None:
        self._responses = list(responses)
        self._model = model
        self.calls = 0
        self.last_messages: tuple[LlmMessage, ...] = ()

    @property
    def model(self) -> str:
        return self._model

    async def complete(
        self,
        messages: tuple[LlmMessage, ...],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> LlmResponse:
        self.calls += 1
        self.last_messages = messages
        if not self._responses:
            raise RuntimeError("no fake response configured")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LlmResponse(content=item, model=self._model)


class SlowLlm:
    @property
    def model(self) -> str:
        return "slow-llm"

    async def complete(
        self,
        messages: tuple[LlmMessage, ...],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> LlmResponse:
        await asyncio.sleep(0.1)
        return LlmResponse(content='{"justification":"ok"}', model="slow-llm")
