from paysentineliq.domain.ports.retrieval import (
    ModelStatus,
    RerankResult,
    SparseVector,
)


class FakeEmbedder:
    def __init__(self, *, error: str | None = None) -> None:
        self.loads = 0
        self.closes = 0
        self._error = error
        self._loaded = False

    @property
    def status(self) -> ModelStatus:
        return ModelStatus(
            model_id="fake-embedder",
            backend="onnx",
            loaded=self._loaded,
            error=None if self._loaded else self._error or "not_loaded",
        )

    @property
    def sparse_status(self) -> ModelStatus:
        return ModelStatus(
            model_id="fake-embedder",
            backend="onnx",
            loaded=self._loaded,
            error=None if self._loaded else self._error or "not_loaded",
        )

    def load(self) -> None:
        self.loads += 1
        self._loaded = self._error is None

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple((1.0, 0.0) for _ in texts)

    async def embed_sparse(self, texts: tuple[str, ...]) -> tuple[SparseVector, ...]:
        return tuple(SparseVector(()) for _ in texts)

    async def aclose(self) -> None:
        self.closes += 1


class FakeReranker:
    def __init__(self) -> None:
        self.loads = 0
        self.closes = 0
        self._loaded = False

    @property
    def status(self) -> ModelStatus:
        return ModelStatus(
            model_id="fake-reranker",
            backend="onnx",
            loaded=self._loaded,
            error=None if self._loaded else "not_loaded",
        )

    def load(self) -> None:
        self.loads += 1
        self._loaded = True

    async def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]:
        return tuple(RerankResult(index=index, score=0.5) for index in range(len(documents)))

    async def aclose(self) -> None:
        self.closes += 1
