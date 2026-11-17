import asyncio
import logging
from dataclasses import dataclass
from datetime import date

from paysentineliq.application.ports.hybrid_vector_store import HybridVectorStorePort
from paysentineliq.application.queries.knowledge_retrieval import (
    KnowledgeQuery,
    KnowledgeRetrievalResult,
    RetrievedPassage,
    citation_from_chunk,
)
from paysentineliq.domain.knowledge import KnowledgeFilter, RetrievedChunk
from paysentineliq.domain.ports.retrieval import (
    Embedder,
    HybridEmbedder,
    SparseEmbedder,
    SparseVector,
)

_logger = logging.getLogger("paysentineliq")


@dataclass(frozen=True, slots=True)
class FusedPassage:
    chunk: RetrievedChunk
    fused_score: float
    dense_score: float | None
    sparse_score: float | None
    dense_rank: int | None
    sparse_rank: int | None


def _key(chunk: RetrievedChunk) -> tuple[str, int, str]:
    return (chunk.document_key, chunk.chunk_index, chunk.content_hash)


def _ordered(entries: dict[tuple[str, int, str], FusedPassage]) -> tuple[FusedPassage, ...]:
    return tuple(
        sorted(
            entries.values(),
            key=lambda item: (
                -item.fused_score,
                item.chunk.document_key,
                item.chunk.chunk_index,
            ),
        ),
    )


def fuse_rrf(
    dense: tuple[RetrievedChunk, ...],
    sparse: tuple[RetrievedChunk, ...],
    *,
    rrf_k: int,
) -> tuple[FusedPassage, ...]:
    if rrf_k <= 0:
        raise ValueError("rrf_k must be positive")
    entries: dict[tuple[str, int, str], FusedPassage] = {}
    for rank, chunk in enumerate(dense, start=1):
        key = _key(chunk)
        entries[key] = FusedPassage(
            chunk=chunk,
            fused_score=1.0 / (rrf_k + rank),
            dense_score=chunk.score,
            sparse_score=None,
            dense_rank=rank,
            sparse_rank=None,
        )
    for rank, chunk in enumerate(sparse, start=1):
        key = _key(chunk)
        current = entries.get(key)
        contribution = 1.0 / (rrf_k + rank)
        if current is None:
            entries[key] = FusedPassage(
                chunk=chunk,
                fused_score=contribution,
                dense_score=None,
                sparse_score=chunk.score,
                dense_rank=None,
                sparse_rank=rank,
            )
        else:
            entries[key] = FusedPassage(
                chunk=current.chunk,
                fused_score=current.fused_score + contribution,
                dense_score=current.dense_score,
                sparse_score=chunk.score,
                dense_rank=current.dense_rank,
                sparse_rank=rank,
            )
    return _ordered(entries)


def fuse_weighted(
    dense: tuple[RetrievedChunk, ...],
    sparse: tuple[RetrievedChunk, ...],
    *,
    dense_weight: float,
    sparse_weight: float,
) -> tuple[FusedPassage, ...]:
    if dense_weight < 0 or sparse_weight < 0:
        raise ValueError("fusion weights must be non-negative")
    if dense_weight == 0 and sparse_weight == 0:
        raise ValueError("at least one fusion weight must be positive")
    entries: dict[tuple[str, int, str], FusedPassage] = {}
    for rank, chunk in enumerate(dense, start=1):
        normalized = min(1.0, max(0.0, chunk.score))
        entries[_key(chunk)] = FusedPassage(
            chunk=chunk,
            fused_score=dense_weight * normalized,
            dense_score=chunk.score,
            sparse_score=None,
            dense_rank=rank,
            sparse_rank=None,
        )
    max_sparse = max((chunk.score for chunk in sparse), default=0.0)
    for rank, chunk in enumerate(sparse, start=1):
        normalized = chunk.score / max_sparse if max_sparse > 0 else 0.0
        key = _key(chunk)
        current = entries.get(key)
        contribution = sparse_weight * normalized
        if current is None:
            entries[key] = FusedPassage(
                chunk=chunk,
                fused_score=contribution,
                dense_score=None,
                sparse_score=chunk.score,
                dense_rank=None,
                sparse_rank=rank,
            )
        else:
            entries[key] = FusedPassage(
                chunk=current.chunk,
                fused_score=current.fused_score + contribution,
                dense_score=current.dense_score,
                sparse_score=chunk.score,
                dense_rank=current.dense_rank,
                sparse_rank=rank,
            )
    return _ordered(entries)


class HybridRetriever:
    def __init__(
        self,
        embedder: Embedder,
        sparse_embedder: SparseEmbedder,
        store: HybridVectorStorePort,
        *,
        hybrid_embedder: HybridEmbedder | None = None,
        default_limit: int = 25,
        fusion: str = "rrf",
        rrf_k: int = 60,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
    ) -> None:
        if default_limit <= 0:
            raise ValueError("default_limit must be positive")
        if fusion not in ("rrf", "weighted"):
            raise ValueError("fusion must be rrf or weighted")
        if rrf_k <= 0:
            raise ValueError("rrf_k must be positive")
        if dense_weight < 0 or sparse_weight < 0:
            raise ValueError("fusion weights must be non-negative")
        if dense_weight == 0 and sparse_weight == 0:
            raise ValueError("at least one fusion weight must be positive")
        self._embedder = embedder
        self._sparse_embedder = sparse_embedder
        self._store = store
        self._hybrid_embedder = hybrid_embedder
        self._default_limit = default_limit
        self._fusion = fusion
        self._rrf_k = rrf_k
        self._dense_weight = dense_weight
        self._sparse_weight = sparse_weight

    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeRetrievalResult:
        limit = query.limit or self._default_limit
        filters = KnowledgeFilter(
            categories=query.categories,
            as_of=query.as_of or date.today(),
        )
        dense_vector, sparse_vector = await self._query_vectors(query.text)
        if dense_vector is None and sparse_vector is None:
            return KnowledgeRetrievalResult(
                passages=(),
                rag_unavailable=True,
                reason="rag_unavailable",
            )

        dense_chunks, sparse_chunks, dense_ok, sparse_ok = await self._search(
            dense_vector,
            sparse_vector,
            limit=limit,
            filters=filters,
        )
        if not dense_ok and not sparse_ok:
            return KnowledgeRetrievalResult(
                passages=(),
                rag_unavailable=True,
                reason="rag_unavailable",
            )

        if dense_ok and sparse_ok:
            fused = (
                fuse_rrf(dense_chunks, sparse_chunks, rrf_k=self._rrf_k)
                if self._fusion == "rrf"
                else fuse_weighted(
                    dense_chunks,
                    sparse_chunks,
                    dense_weight=self._dense_weight,
                    sparse_weight=self._sparse_weight,
                )
            )
            mode = f"hybrid_{self._fusion}"
        elif dense_ok:
            fused = tuple(
                FusedPassage(
                    chunk=chunk,
                    fused_score=chunk.score,
                    dense_score=chunk.score,
                    sparse_score=None,
                    dense_rank=rank,
                    sparse_rank=None,
                )
                for rank, chunk in enumerate(dense_chunks, start=1)
            )
            mode = "dense"
        else:
            fused = tuple(
                FusedPassage(
                    chunk=chunk,
                    fused_score=chunk.score,
                    dense_score=None,
                    sparse_score=chunk.score,
                    dense_rank=None,
                    sparse_rank=rank,
                )
                for rank, chunk in enumerate(sparse_chunks, start=1)
            )
            mode = "sparse"

        passages = tuple(
            RetrievedPassage(
                content=item.chunk.content,
                citation=citation_from_chunk(item.chunk),
                score=item.fused_score,
                dense_score=item.dense_score,
                sparse_score=item.sparse_score,
                fused_score=item.fused_score,
                dense_rank=item.dense_rank,
                sparse_rank=item.sparse_rank,
            )
            for item in fused[:limit]
        )
        return KnowledgeRetrievalResult(
            passages=passages,
            rag_unavailable=False,
            reason=None,
            retrieval_mode=mode,
        )

    async def _query_vectors(
        self,
        text: str,
    ) -> tuple[tuple[float, ...] | None, SparseVector | None]:
        if self._hybrid_embedder is not None:
            try:
                dense, sparse = await self._hybrid_embedder.embed_hybrid((text,))
                if len(dense) == 1 and len(sparse) == 1:
                    return self._valid_dense(dense[0]), sparse[0]
            except Exception:
                _logger.warning("hybrid_embedder_failed")
        results = await asyncio.gather(
            self._embedder.embed((text,)),
            self._sparse_embedder.embed_sparse((text,)),
            return_exceptions=True,
        )
        dense_vector: tuple[float, ...] | None = None
        sparse_vector: SparseVector | None = None
        dense_result, sparse_result = results
        if not isinstance(dense_result, BaseException) and len(dense_result) == 1:
            dense_vector = self._valid_dense(dense_result[0])
        else:
            _logger.warning("hybrid_dense_embedding_unavailable")
        if not isinstance(sparse_result, BaseException) and len(sparse_result) == 1:
            sparse_vector = sparse_result[0]
        else:
            _logger.warning("hybrid_sparse_embedding_unavailable")
        return dense_vector, sparse_vector

    def _valid_dense(self, vector: tuple[float, ...]) -> tuple[float, ...] | None:
        if len(vector) != self._embedder.dimension:
            _logger.warning("hybrid_dense_dimension_mismatch")
            return None
        return vector

    async def _search(
        self,
        dense_vector: tuple[float, ...] | None,
        sparse_vector: SparseVector | None,
        *,
        limit: int,
        filters: KnowledgeFilter,
    ) -> tuple[
        tuple[RetrievedChunk, ...],
        tuple[RetrievedChunk, ...],
        bool,
        bool,
    ]:
        tasks: list[asyncio.Future[tuple[RetrievedChunk, ...]]] = []
        kinds: list[str] = []
        if dense_vector is not None:
            tasks.append(
                asyncio.ensure_future(
                    self._store.dense_query(
                        dense_vector,
                        limit=limit,
                        filters=filters,
                    ),
                ),
            )
            kinds.append("dense")
        if sparse_vector is not None:
            tasks.append(
                asyncio.ensure_future(
                    self._store.sparse_query(
                        sparse_vector,
                        limit=limit,
                        filters=filters,
                    ),
                ),
            )
            kinds.append("sparse")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        dense_chunks: tuple[RetrievedChunk, ...] = ()
        sparse_chunks: tuple[RetrievedChunk, ...] = ()
        dense_ok = dense_vector is not None
        sparse_ok = sparse_vector is not None
        for kind, result in zip(kinds, results, strict=True):
            if isinstance(result, BaseException):
                if kind == "dense":
                    dense_ok = False
                else:
                    sparse_ok = False
                _logger.warning("hybrid_%s_query_failed", kind)
                continue
            if kind == "dense":
                dense_chunks = result
            else:
                sparse_chunks = result
        return dense_chunks, sparse_chunks, dense_ok, sparse_ok
