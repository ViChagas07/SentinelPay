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
)
from paysentineliq.domain.ports.retrieval import Reranker

_logger = logging.getLogger("paysentineliq")


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
                    return self._fallback(result, "timeout", span)
                except Exception:
                    _logger.warning("retrieval_rerank_failed")
                    rerank_span.set_attribute("retrieval.rerank.outcome", "error")
                    return self._fallback(result, "error", span)
                if not reranked:
                    rerank_span.set_attribute("retrieval.rerank.outcome", "empty")
                    return self._fallback(result, "empty", span)
                indices = [item.index for item in reranked]
                if len(set(indices)) != len(indices) or any(
                    index >= len(result.passages) for index in indices
                ):
                    rerank_span.set_attribute("retrieval.rerank.outcome", "error")
                    return self._fallback(result, "error", span)
                selected = tuple(
                    replace(
                        result.passages[item.index],
                        score=item.score,
                        rerank_score=item.score,
                    )
                    for item in reranked[: self._top_n]
                )
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
            retrieval_mode=f"{result.retrieval_mode}_reranked",
        )

    def _fallback(
        self,
        result: KnowledgeRetrievalResult,
        reason: str,
        span: Span,
    ) -> KnowledgeRetrievalResult:
        passages = result.passages[: self._top_n]
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
            retrieval_mode=f"{result.retrieval_mode}_fallback",
        )
