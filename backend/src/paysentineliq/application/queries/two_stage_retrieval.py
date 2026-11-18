import asyncio
import logging
from dataclasses import replace
from time import perf_counter

from opentelemetry import trace
from opentelemetry.trace import Span, Tracer

from paysentineliq.application.errors import RerankTimeoutError
from paysentineliq.application.ports.rag import RagContextPort
from paysentineliq.application.ports.retrieval_metrics import (
    NullRetrievalMetrics,
    RetrievalMetricsPort,
)
from paysentineliq.application.queries.knowledge_retrieval import (
    KnowledgeQuery,
    KnowledgeRetrievalResult,
    RetrievedPassage,
)
from paysentineliq.domain.ports.observability import ObservabilityTracer
from paysentineliq.domain.ports.retrieval import Reranker

_logger = logging.getLogger("paysentineliq")


def _rank_snapshot(passages: tuple[RetrievedPassage, ...]) -> tuple[str, ...]:
    return tuple(f"{passage.citation.document_key}|{passage.score:.6f}" for passage in passages)


def _top1_changed(before: tuple[str, ...], after: tuple[str, ...]) -> bool:
    if not before or not after:
        return False
    return before[0].split("|", 1)[0] != after[0].split("|", 1)[0]


class TwoStageRetriever:
    def __init__(
        self,
        stage1: RagContextPort,
        *,
        reranker: Reranker | None,
        rerank_enabled: bool,
        top_n: int,
        timeout_seconds: float,
        metrics: RetrievalMetricsPort | None = None,
        tracer: Tracer | None = None,
        observability: ObservabilityTracer | None = None,
    ) -> None:
        if top_n <= 0:
            raise ValueError("top_n must be positive")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._stage1 = stage1
        self._reranker = reranker
        self._rerank_enabled = rerank_enabled
        self._top_n = top_n
        self._timeout_seconds = timeout_seconds
        self._metrics = metrics or NullRetrievalMetrics()
        self._tracer = tracer or trace.get_tracer("paysentineliq.retrieval")
        self._observability = observability

    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeRetrievalResult:
        total_started = perf_counter()
        with self._tracer.start_as_current_span("retrieval.two_stage") as span:
            span.set_attribute("retrieval.rerank_enabled", self._rerank_enabled)
            span.set_attribute("retrieval.top_n", self._top_n)
            try:
                result = await self._run_stage1(query)
                span.set_attribute("retrieval.candidates", len(result.passages))
                if result.rag_unavailable:
                    span.set_attribute("retrieval.rag_unavailable", True)
                    return result
                if not self._rerank_enabled:
                    self._metrics.record_rerank_outcome("disabled")
                    span.set_attribute("retrieval.rerank.outcome", "disabled")
                    return replace(result, rerank_fallback="disabled")
                if self._reranker is None:
                    return self._fallback(result, "unavailable", span)
                return await self._rerank(result, query, span)
            finally:
                duration = perf_counter() - total_started
                self._metrics.record_retrieval_stage("total", duration)
                span.set_attribute("retrieval.duration_seconds", duration)

    async def _run_stage1(self, query: KnowledgeQuery) -> KnowledgeRetrievalResult:
        if self._observability is None:
            return await self._run_stage1_inner(query)
        with self._observability.observation(
            "retrieval.stage1",
            as_type="retriever",
            input={"query_chars": len(query.text), "limit": query.limit},
            metadata={"top_k": self._top_n},
        ) as observation:
            result = await self._run_stage1_inner(query)
            observation.update(
                output={
                    "candidates": len(result.passages),
                    "rag_unavailable": result.rag_unavailable,
                    "scores": [
                        {
                            "document_key": passage.citation.document_key,
                            "score": passage.score,
                            "dense_score": passage.dense_score,
                            "sparse_score": passage.sparse_score,
                            "fused_score": passage.fused_score,
                            "dense_rank": passage.dense_rank,
                            "sparse_rank": passage.sparse_rank,
                        }
                        for passage in result.passages
                    ],
                },
            )
            return result

    async def _run_stage1_inner(self, query: KnowledgeQuery) -> KnowledgeRetrievalResult:
        started = perf_counter()
        with self._tracer.start_as_current_span("retrieval.stage1"):
            try:
                result = await self._stage1.retrieve(query)
            except Exception:
                _logger.warning("retrieval_stage1_failed")
                result = KnowledgeRetrievalResult(
                    passages=(),
                    rag_unavailable=True,
                    reason="rag_unavailable",
                )
        self._metrics.record_retrieval_stage("stage1", perf_counter() - started)
        self._metrics.record_retrieval_candidates("stage1", len(result.passages))
        for passage in result.passages:
            self._metrics.record_retrieval_score("stage1", passage.score)
        return result

    async def _rerank(
        self,
        result: KnowledgeRetrievalResult,
        query: KnowledgeQuery,
        span: Span,
    ) -> KnowledgeRetrievalResult:
        if self._observability is None:
            return await self._rerank_inner(result, query, span)
        before = _rank_snapshot(result.passages)
        with self._observability.observation(
            "retrieval.rerank",
            as_type="retriever",
            input={"candidates": len(result.passages)},
            metadata={
                "top_n": self._top_n,
                "model": self._reranker.model_id if self._reranker is not None else None,
            },
        ) as observation:
            reranked = await self._rerank_inner(result, query, span)
            observation.update(
                output={
                    "order_before": list(before),
                    "order_after": list(reranked.rerank_rank_after),
                    "latency_ms": reranked.rerank_latency_ms,
                    "top1_changed": reranked.rerank_top1_changed,
                    "outcome": ("success" if reranked.rerank_applied else reranked.rerank_fallback),
                },
                metadata={"model": reranked.rerank_model},
            )
            return reranked

    async def _rerank_inner(
        self,
        result: KnowledgeRetrievalResult,
        query: KnowledgeQuery,
        span: Span,
    ) -> KnowledgeRetrievalResult:
        if self._reranker is None:
            return self._fallback(result, "unavailable", span)
        documents = tuple(passage.content for passage in result.passages)
        started = perf_counter()
        try:
            with self._tracer.start_as_current_span("retrieval.rerank") as rerank_span:
                rerank_span.set_attribute("retrieval.candidates", len(documents))
                rerank_span.set_attribute("retrieval.top_n", self._top_n)
                try:
                    reranked = await asyncio.wait_for(
                        self._reranker.rerank(
                            query.text,
                            documents,
                            top_n=self._top_n,
                        ),
                        timeout=self._timeout_seconds,
                    )
                except (TimeoutError, RerankTimeoutError):
                    rerank_span.set_attribute("retrieval.rerank.outcome", "timeout")
                    return self._fallback(
                        result,
                        "timeout",
                        span,
                        (perf_counter() - started) * 1000.0,
                    )
                except Exception:
                    _logger.warning("retrieval_rerank_failed")
                    rerank_span.set_attribute("retrieval.rerank.outcome", "error")
                    return self._fallback(
                        result,
                        "error",
                        span,
                        (perf_counter() - started) * 1000.0,
                    )
                if not reranked:
                    rerank_span.set_attribute("retrieval.rerank.outcome", "empty")
                    return self._fallback(
                        result,
                        "empty",
                        span,
                        (perf_counter() - started) * 1000.0,
                    )
                indices = [item.index for item in reranked]
                if len(set(indices)) != len(indices) or any(
                    index >= len(result.passages) for index in indices
                ):
                    rerank_span.set_attribute("retrieval.rerank.outcome", "error")
                    return self._fallback(
                        result,
                        "error",
                        span,
                        (perf_counter() - started) * 1000.0,
                    )
                selected = tuple(
                    replace(
                        result.passages[item.index],
                        score=item.score,
                        rerank_score=item.score,
                    )
                    for item in reranked[: self._top_n]
                )
                latency_ms = (perf_counter() - started) * 1000.0
                before = _rank_snapshot(result.passages)
                after = _rank_snapshot(selected)
                rerank_span.set_attribute("retrieval.reranked", len(selected))
                rerank_span.set_attribute("retrieval.rerank.outcome", "success")
                rerank_span.set_attribute("retrieval.rerank.model", self._reranker.model_id)
        finally:
            self._metrics.record_retrieval_stage("rerank", perf_counter() - started)
        self._metrics.record_retrieval_candidates("reranked", len(selected))
        for passage in selected:
            self._metrics.record_retrieval_score("reranked", passage.score)
        self._metrics.record_rerank_outcome("success")
        span.set_attribute("retrieval.reranked", len(selected))
        span.set_attribute("retrieval.rerank.outcome", "success")
        span.set_attribute("retrieval.rerank.model", self._reranker.model_id)
        return replace(
            result,
            passages=selected,
            rerank_applied=True,
            rerank_fallback=None,
            rerank_model=self._reranker.model_id,
            rerank_rank_before=before,
            rerank_rank_after=after,
            rerank_latency_ms=latency_ms,
            rerank_top1_changed=_top1_changed(before, after),
            retrieval_mode=f"{result.retrieval_mode}_reranked",
        )

    def _fallback(
        self,
        result: KnowledgeRetrievalResult,
        reason: str,
        span: Span,
        latency_ms: float | None = None,
    ) -> KnowledgeRetrievalResult:
        passages = result.passages[: self._top_n]
        before = _rank_snapshot(result.passages)
        after = _rank_snapshot(passages)
        self._metrics.record_retrieval_candidates("reranked", len(passages))
        for passage in passages:
            self._metrics.record_retrieval_score("reranked", passage.score)
        self._metrics.record_rerank_outcome(reason)
        span.set_attribute("retrieval.reranked", len(passages))
        span.set_attribute("retrieval.rerank.outcome", reason)
        model_id = self._reranker.model_id if self._reranker is not None else None
        if model_id is not None:
            span.set_attribute("retrieval.rerank.model", model_id)
        return replace(
            result,
            passages=passages,
            rerank_applied=False,
            rerank_fallback=reason,
            rerank_model=model_id,
            rerank_rank_before=before,
            rerank_rank_after=after,
            rerank_latency_ms=latency_ms,
            rerank_top1_changed=False,
            retrieval_mode=f"{result.retrieval_mode}_fallback",
        )
