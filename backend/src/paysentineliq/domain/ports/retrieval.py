from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from paysentineliq.domain.knowledge import KnowledgeChunk

DENSE_EMBEDDING_DIMENSION = 1024


@dataclass(frozen=True, slots=True)
class SparseVector:
    weights: tuple[tuple[int, float], ...]

    def __post_init__(self) -> None:
        previous = -1
        for token_id, weight in self.weights:
            if token_id <= previous:
                raise ValueError("sparse token ids must be strictly increasing")
            if not isfinite(weight) or weight <= 0.0:
                raise ValueError("sparse weights must be finite and positive")
            previous = token_id

    def as_dict(self) -> dict[int, float]:
        return dict(self.weights)


@dataclass(frozen=True, slots=True)
class RerankResult:
    index: int
    score: float

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("rerank index must be non-negative")
        if not isfinite(self.score) or not 0.0 <= self.score <= 1.0:
            raise ValueError("rerank score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ModelStatus:
    model_id: str
    backend: str
    loaded: bool
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id must not be empty")
        if self.backend not in ("onnx", "pytorch", "remote"):
            raise ValueError("backend must be onnx, pytorch or remote")
        if self.loaded and self.error is not None:
            raise ValueError("loaded models cannot carry an error")


@dataclass(frozen=True, slots=True)
class RetrievalStatus:
    top_k: int
    rerank_top_n: int
    rerank_enabled: bool
    embedder: ModelStatus
    sparse_embedder: ModelStatus
    reranker: ModelStatus | None

    def __post_init__(self) -> None:
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")
        if self.rerank_top_n <= 0:
            raise ValueError("rerank_top_n must be positive")
        if self.rerank_top_n > self.top_k:
            raise ValueError("rerank_top_n must not exceed top_k")
        if self.rerank_enabled and self.reranker is None:
            raise ValueError("enabled reranker requires a model status")
        if not self.rerank_enabled and self.reranker is not None:
            raise ValueError("disabled reranker must not expose a model status")


@dataclass(frozen=True, slots=True)
class HybridEmbeddedChunk:
    chunk: KnowledgeChunk
    dense_embedding: tuple[float, ...]
    sparse_embedding: SparseVector

    def __post_init__(self) -> None:
        if not self.dense_embedding:
            raise ValueError("dense embedding must not be empty")
        if not all(isfinite(value) for value in self.dense_embedding):
            raise ValueError("dense embedding must be finite")


class Embedder(Protocol):
    @property
    def dimension(self) -> int: ...

    @property
    def model_id(self) -> str: ...

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...


class HybridEmbedder(Protocol):
    @property
    def dimension(self) -> int: ...

    @property
    def model_id(self) -> str: ...

    async def embed_hybrid(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[tuple[float, ...], ...], tuple[SparseVector, ...]]: ...


class SparseEmbedder(Protocol):
    @property
    def model_id(self) -> str: ...

    async def embed_sparse(self, texts: tuple[str, ...]) -> tuple[SparseVector, ...]: ...


class Reranker(Protocol):
    @property
    def model_id(self) -> str: ...

    async def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]: ...


class RetrievalStatusProvider(Protocol):
    @property
    def status(self) -> RetrievalStatus: ...
