from typing import Protocol


class RetrievalMetricsPort(Protocol):
    def record_retrieval_stage(self, stage: str, duration_seconds: float) -> None: ...

    def record_retrieval_candidates(self, stage: str, count: int) -> None: ...

    def record_retrieval_score(self, stage: str, score: float) -> None: ...

    def record_rerank_outcome(self, outcome: str) -> None: ...


class NullRetrievalMetrics:
    def record_retrieval_stage(self, stage: str, duration_seconds: float) -> None:
        del stage, duration_seconds

    def record_retrieval_candidates(self, stage: str, count: int) -> None:
        del stage, count

    def record_retrieval_score(self, stage: str, score: float) -> None:
        del stage, score

    def record_rerank_outcome(self, outcome: str) -> None:
        del outcome
