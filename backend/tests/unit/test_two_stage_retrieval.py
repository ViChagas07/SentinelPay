import asyncio
from dataclasses import dataclass, field

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from paysentineliq.application.queries.knowledge_retrieval import (
    KnowledgeCitation,
    KnowledgeQuery,
    KnowledgeRetrievalResult,
    RetrievedPassage,
)
from paysentineliq.application.queries.two_stage_retrieval import TwoStageRetriever
from paysentineliq.domain.knowledge import Provenance
from paysentineliq.domain.ports.retrieval import RerankResult

pytestmark = pytest.mark.unit


def _passage(content: str, score: float) -> RetrievedPassage:
    citation = KnowledgeCitation(
        document_key=f"faq/{content}.pdf",
        path=f"knowledge/faq/{content}.pdf",
        title=content,
        category="faq",
        section="secao",
        provenance=Provenance.OFFICIAL,
        source="oficial",
        version="1",
        authoritative=True,
    )
    return RetrievedPassage(
        content=content,
        citation=citation,
        score=score,
        fused_score=score,
    )


def _result() -> KnowledgeRetrievalResult:
    return KnowledgeRetrievalResult(
        passages=(
            _passage("alpha", 0.03),
            _passage("beta", 0.02),
            _passage("gamma", 0.01),
        ),
        rag_unavailable=False,
        reason=None,
        retrieval_mode="hybrid_rrf",
    )


class FakeStage1:
    def __init__(self, result: KnowledgeRetrievalResult) -> None:
        self.result = result
        self.calls = 0

    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeRetrievalResult:
        del query
        self.calls += 1
        return self.result


class FakeReranker:
    model_id = "fake-reranker"

    def __init__(
        self,
        *,
        results: tuple[RerankResult, ...] = (),
        error: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self.results = results
        self.error = error
        self.delay = delay
        self.calls = 0
        self.query = ""
        self.documents: tuple[str, ...] = ()
        self.top_n: int | None = None

    async def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]:
        self.calls += 1
        self.query = query
        self.documents = documents
        self.top_n = top_n
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.results


@dataclass
class RecordingMetrics:
    stages: list[tuple[str, float]] = field(default_factory=list)
    candidates: list[tuple[str, int]] = field(default_factory=list)
    scores: list[tuple[str, float]] = field(default_factory=list)
    outcomes: list[str] = field(default_factory=list)

    def record_retrieval_stage(self, stage: str, duration_seconds: float) -> None:
        self.stages.append((stage, duration_seconds))

    def record_retrieval_candidates(self, stage: str, count: int) -> None:
        self.candidates.append((stage, count))

    def record_retrieval_score(self, stage: str, score: float) -> None:
        self.scores.append((stage, score))

    def record_rerank_outcome(self, outcome: str) -> None:
        self.outcomes.append(outcome)


async def test_two_stage_returns_top_n_reranked_with_scores() -> None:
    metrics = RecordingMetrics()
    reranker = FakeReranker(
        results=(
            RerankResult(index=2, score=0.95),
            RerankResult(index=0, score=0.8),
        ),
    )
    retriever = TwoStageRetriever(
        FakeStage1(_result()),
        reranker=reranker,
        rerank_enabled=True,
        top_n=2,
        timeout_seconds=1.0,
        metrics=metrics,
    )

    result = await retriever.retrieve(KnowledgeQuery(text="consulta", limit=25))

    assert [passage.content for passage in result.passages] == ["gamma", "alpha"]
    assert [passage.score for passage in result.passages] == [0.95, 0.8]
    assert [passage.rerank_score for passage in result.passages] == [0.95, 0.8]
    assert result.passages[0].fused_score == 0.01
    assert result.rerank_applied is True
    assert result.rerank_fallback is None
    assert result.rerank_model == "fake-reranker"
    assert result.retrieval_mode == "hybrid_rrf_reranked"
    assert reranker.query == "consulta"
    assert reranker.documents == ("alpha", "beta", "gamma")
    assert reranker.top_n == 2
    assert metrics.outcomes == ["success"]
    assert ("stage1",) in [(stage,) for stage, _ in metrics.stages]
    assert any(stage == "rerank" for stage, _ in metrics.stages)
    assert any(stage == "total" for stage, _ in metrics.stages)
    assert ("stage1", 3) in metrics.candidates
    assert ("reranked", 2) in metrics.candidates
    assert len([item for item in metrics.scores if item[0] == "stage1"]) == 3
    assert len([item for item in metrics.scores if item[0] == "reranked"]) == 2


async def test_rerank_disabled_keeps_stage_one_order() -> None:
    metrics = RecordingMetrics()
    reranker = FakeReranker(results=(RerankResult(index=2, score=0.95),))
    retriever = TwoStageRetriever(
        FakeStage1(_result()),
        reranker=reranker,
        rerank_enabled=False,
        top_n=2,
        timeout_seconds=1.0,
        metrics=metrics,
    )

    result = await retriever.retrieve(KnowledgeQuery(text="consulta"))

    assert [passage.content for passage in result.passages] == [
        "alpha",
        "beta",
        "gamma",
    ]
    assert result.rerank_applied is False
    assert result.rerank_fallback == "disabled"
    assert result.retrieval_mode == "hybrid_rrf"
    assert reranker.calls == 0
    assert metrics.outcomes == ["disabled"]


async def test_rerank_timeout_falls_back_to_stage_one_order() -> None:
    metrics = RecordingMetrics()
    reranker = FakeReranker(delay=0.05)
    retriever = TwoStageRetriever(
        FakeStage1(_result()),
        reranker=reranker,
        rerank_enabled=True,
        top_n=2,
        timeout_seconds=0.001,
        metrics=metrics,
    )

    result = await retriever.retrieve(KnowledgeQuery(text="consulta"))

    assert [passage.content for passage in result.passages] == ["alpha", "beta"]
    assert result.rerank_applied is False
    assert result.rerank_fallback == "timeout"
    assert result.retrieval_mode == "hybrid_rrf_fallback"
    assert metrics.outcomes == ["timeout"]


@pytest.mark.parametrize(
    ("reranker", "reason"),
    [
        (FakeReranker(error=RuntimeError("offline")), "error"),
        (FakeReranker(results=()), "empty"),
        (FakeReranker(results=(RerankResult(index=99, score=0.5),)), "error"),
        (None, "unavailable"),
    ],
)
async def test_rerank_failures_fall_back_to_stage_one(
    reranker: FakeReranker | None,
    reason: str,
) -> None:
    metrics = RecordingMetrics()
    retriever = TwoStageRetriever(
        FakeStage1(_result()),
        reranker=reranker,
        rerank_enabled=True,
        top_n=2,
        timeout_seconds=1.0,
        metrics=metrics,
    )

    result = await retriever.retrieve(KnowledgeQuery(text="consulta"))

    assert [passage.content for passage in result.passages] == ["alpha", "beta"]
    assert result.rerank_applied is False
    assert result.rerank_fallback == reason
    assert metrics.outcomes == [reason]


async def test_two_stage_records_spans_without_query_text() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    reranker = FakeReranker(results=(RerankResult(index=0, score=0.9),))
    retriever = TwoStageRetriever(
        FakeStage1(_result()),
        reranker=reranker,
        rerank_enabled=True,
        top_n=1,
        timeout_seconds=1.0,
        tracer=tracer,
    )

    await retriever.retrieve(KnowledgeQuery(text="consulta secreta"))

    spans = exporter.get_finished_spans()
    names = {span.name for span in spans}
    assert {
        "retrieval.two_stage",
        "retrieval.stage1",
        "retrieval.rerank",
    } <= names
    rendered = " ".join(str(span.attributes) for span in spans)
    assert "consulta secreta" not in rendered


async def test_stage_one_unavailable_skips_rerank() -> None:
    metrics = RecordingMetrics()
    reranker = FakeReranker(results=(RerankResult(index=0, score=0.9),))
    stage1_result = KnowledgeRetrievalResult(
        passages=(),
        rag_unavailable=True,
        reason="rag_unavailable",
    )
    retriever = TwoStageRetriever(
        FakeStage1(stage1_result),
        reranker=reranker,
        rerank_enabled=True,
        top_n=2,
        timeout_seconds=1.0,
        metrics=metrics,
    )

    result = await retriever.retrieve(KnowledgeQuery(text="consulta"))

    assert result.rag_unavailable is True
    assert result.passages == ()
    assert reranker.calls == 0
    assert metrics.outcomes == []
