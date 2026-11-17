import asyncio
import hashlib
import json
import logging
import math
from collections.abc import Awaitable, Sequence
from typing import Protocol

from paysentineliq.application.errors import EmbeddingDimensionError
from paysentineliq.domain.ports.retrieval import (
    Embedder,
    HybridEmbedder,
    SparseEmbedder,
    SparseVector,
)

_logger = logging.getLogger("paysentineliq")


class AsyncEmbeddingCache(Protocol):
    def mget(self, keys: Sequence[str]) -> Awaitable[Sequence[object]]: ...

    def set(
        self,
        name: str,
        value: str,
        ex: int | None = None,
    ) -> Awaitable[object]: ...


class CachedEmbedder:
    def __init__(
        self,
        embedder: Embedder,
        sparse_embedder: SparseEmbedder,
        cache: AsyncEmbeddingCache,
        *,
        ttl_seconds: int = 3600,
        namespace: str = "paysentineliq:query-embedding:v1",
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if not namespace.strip():
            raise ValueError("namespace must not be empty")
        self._embedder = embedder
        self._sparse_embedder = sparse_embedder
        self._cache = cache
        self._ttl_seconds = ttl_seconds
        self._namespace = namespace

    @property
    def dimension(self) -> int:
        return self._embedder.dimension

    @property
    def model_id(self) -> str:
        return self._embedder.model_id

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        keys = tuple(self._key("dense", text) for text in texts)
        cached = await self._safe_mget(keys)
        vectors: list[tuple[float, ...] | None] = [self._decode_dense(value) for value in cached]
        missing = [(index, text) for index, text in enumerate(texts) if vectors[index] is None]
        if missing:
            generated = await self._embedder.embed(
                tuple(text for _, text in missing),
            )
            if len(generated) != len(missing):
                raise EmbeddingDimensionError("embedding count mismatch")
            writes: list[tuple[str, str]] = []
            for (index, _), vector in zip(missing, generated, strict=True):
                if len(vector) != self.dimension:
                    raise EmbeddingDimensionError("embedding dimension mismatch")
                vectors[index] = vector
                writes.append((keys[index], json.dumps(list(vector), separators=(",", ":"))))
            await self._safe_set(writes)
        resolved = tuple(vector for vector in vectors if vector is not None)
        if len(resolved) != len(texts):
            raise EmbeddingDimensionError("embedding cache resolution failed")
        return resolved

    async def embed_sparse(self, texts: tuple[str, ...]) -> tuple[SparseVector, ...]:
        if not texts:
            return ()
        keys = tuple(self._key("sparse", text) for text in texts)
        cached = await self._safe_mget(keys)
        vectors: list[SparseVector | None] = [self._decode_sparse(value) for value in cached]
        missing = [(index, text) for index, text in enumerate(texts) if vectors[index] is None]
        if missing:
            generated = await self._sparse_embedder.embed_sparse(
                tuple(text for _, text in missing),
            )
            if len(generated) != len(missing):
                raise EmbeddingDimensionError("sparse embedding count mismatch")
            writes: list[tuple[str, str]] = []
            for (index, _), vector in zip(missing, generated, strict=True):
                vectors[index] = vector
                writes.append(
                    (
                        keys[index],
                        json.dumps(
                            [[token_id, weight] for token_id, weight in vector.weights],
                            separators=(",", ":"),
                        ),
                    ),
                )
            await self._safe_set(writes)
        resolved = tuple(vector for vector in vectors if vector is not None)
        if len(resolved) != len(texts):
            raise EmbeddingDimensionError("sparse cache resolution failed")
        return resolved

    async def embed_hybrid(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[tuple[float, ...], ...], tuple[SparseVector, ...]]:
        dense, sparse = await asyncio.gather(
            self.embed(texts),
            self.embed_sparse(texts),
        )
        return dense, sparse

    async def aclose(self) -> None:
        closed: set[int] = set()
        for model in (self._embedder, self._sparse_embedder):
            if id(model) in closed:
                continue
            close = getattr(model, "aclose", None)
            if callable(close):
                await close()
            closed.add(id(model))

    def _key(self, kind: str, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        model_id = self._sparse_embedder.model_id if kind == "sparse" else self.model_id
        return f"{self._namespace}:{kind}:{model_id}:{digest}"

    async def _safe_mget(self, keys: tuple[str, ...]) -> tuple[object | None, ...]:
        try:
            values = await self._cache.mget(keys)
        except Exception:
            _logger.warning("query_embedding_cache_read_failed")
            return tuple(None for _ in keys)
        if len(values) != len(keys):
            return tuple(None for _ in keys)
        return tuple(values)

    async def _safe_set(self, writes: list[tuple[str, str]]) -> None:
        if not writes:
            return
        failed = False
        for key, value in writes:
            try:
                await self._cache.set(key, value, ex=self._ttl_seconds)
            except Exception:
                failed = True
        if failed:
            _logger.warning("query_embedding_cache_write_failed")

    def _decode_dense(self, value: object) -> tuple[float, ...] | None:
        payload = self._decode(value)
        if not isinstance(payload, list):
            return None
        if len(payload) != self.dimension:
            return None
        vector: list[float] = []
        for item in payload:
            if not isinstance(item, int | float) or not math.isfinite(float(item)):
                return None
            vector.append(float(item))
        return tuple(vector)

    def _decode_sparse(self, value: object) -> SparseVector | None:
        payload = self._decode(value)
        if not isinstance(payload, list):
            return None
        weights: list[tuple[int, float]] = []
        for item in payload:
            if not isinstance(item, list) or len(item) != 2:
                return None
            token_id, weight = item
            if not isinstance(token_id, int) or not isinstance(weight, int | float):
                return None
            if token_id < 0 or not math.isfinite(float(weight)) or float(weight) <= 0:
                return None
            weights.append((token_id, float(weight)))
        try:
            return SparseVector(tuple(weights))
        except ValueError:
            return None

    def _decode(self, value: object) -> object:
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError:
                return None
        if not isinstance(value, str):
            return None
        try:
            return json.loads(value)
        except ValueError:
            return None


def hybrid_cached(embedder: CachedEmbedder) -> HybridEmbedder:
    return embedder
