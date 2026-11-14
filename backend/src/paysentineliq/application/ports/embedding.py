from typing import Protocol


class EmbeddingPort(Protocol):
    @property
    def dimension(self) -> int: ...

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...
