import asyncio
import logging
from pathlib import Path
from typing import Protocol

from paysentineliq.domain.ports.retrieval import (
    ModelStatus,
    RerankResult,
    RetrievalStatus,
    SparseVector,
)
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.retrieval.bge_m3 import BgeM3Embedder
from paysentineliq.infrastructure.retrieval.bge_reranker import BgeRerankerV2M3

_logger = logging.getLogger("paysentineliq")


class LocalEmbedderModel(Protocol):
    @property
    def status(self) -> ModelStatus: ...

    @property
    def sparse_status(self) -> ModelStatus: ...

    def load(self) -> None: ...

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...

    async def embed_sparse(self, texts: tuple[str, ...]) -> tuple[SparseVector, ...]: ...

    async def aclose(self) -> None: ...


class LocalRerankerModel(Protocol):
    @property
    def status(self) -> ModelStatus: ...

    def load(self) -> None: ...

    async def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]: ...

    async def aclose(self) -> None: ...


class RetrievalRuntime:
    def __init__(
        self,
        settings: Settings,
        *,
        embedder: LocalEmbedderModel | None = None,
        reranker: LocalRerankerModel | None = None,
    ) -> None:
        model_root = Path(settings.retrieval_model_dir)
        self._settings = settings
        self._embedder: LocalEmbedderModel = embedder or BgeM3Embedder(
            model_dir=model_root / "bge-m3",
            backend=settings.embedder_backend,
            batch_size=settings.batch_size,
            torch_num_threads=settings.torch_num_threads,
        )
        self._reranker: LocalRerankerModel | None = None
        if settings.rerank_enabled:
            self._reranker = reranker or BgeRerankerV2M3(
                model_dir=model_root / "bge-reranker-v2-m3",
                backend=settings.reranker_backend,
                batch_size=settings.batch_size,
                max_length=settings.rerank_max_length,
                torch_num_threads=settings.torch_num_threads,
            )
        self._load_lock = asyncio.Lock()
        self._load_attempted = False
        self._closed = False

    @property
    def embedder(self) -> LocalEmbedderModel:
        return self._embedder

    @property
    def sparse_embedder(self) -> LocalEmbedderModel:
        return self._embedder

    @property
    def reranker(self) -> LocalRerankerModel | None:
        return self._reranker

    @property
    def load_attempted(self) -> bool:
        return self._load_attempted

    @property
    def status(self) -> RetrievalStatus:
        return RetrievalStatus(
            top_k=self._settings.retrieval_top_k,
            rerank_top_n=self._settings.rerank_top_n,
            rerank_enabled=self._settings.rerank_enabled,
            embedder=self._embedder.status,
            sparse_embedder=self._embedder.sparse_status,
            reranker=self._reranker.status if self._reranker is not None else None,
        )

    async def load(self) -> None:
        async with self._load_lock:
            if self._load_attempted:
                return
            self._load_attempted = True
            try:
                await asyncio.to_thread(self._embedder.load)
                if self._reranker is not None:
                    await asyncio.to_thread(self._reranker.load)
            except Exception:
                _logger.exception("retrieval_runtime_load_failed")

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._embedder.aclose()
        if self._reranker is not None:
            await self._reranker.aclose()
