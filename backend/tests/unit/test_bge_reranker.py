from pathlib import Path

import pytest

from paysentineliq.application.errors import RetrievalUnavailableError
from paysentineliq.infrastructure.retrieval.bge_reranker import (
    BgeRerankerV2M3,
    rank_scores,
    sigmoid,
)

pytestmark = pytest.mark.unit


def test_rank_scores_sorts_by_score_and_keeps_original_index() -> None:
    results = rank_scores([0.2, 0.9, 0.5], top_n=None)

    assert [result.index for result in results] == [1, 2, 0]
    assert [result.score for result in results] == [0.9, 0.5, 0.2]


def test_rank_scores_applies_top_n_and_stable_ties() -> None:
    results = rank_scores([0.5, 0.5, 0.9], top_n=2)

    assert [result.index for result in results] == [2, 0]


def test_rank_scores_rejects_invalid_top_n() -> None:
    with pytest.raises(ValueError):
        rank_scores([0.5], top_n=0)


def test_sigmoid_maps_logits_to_probabilities() -> None:
    assert sigmoid(0.0) == pytest.approx(0.5)
    assert sigmoid(1000.0) == pytest.approx(1.0)
    assert sigmoid(-1000.0) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        sigmoid(float("nan"))


def test_reranker_reports_missing_files_without_raising(tmp_path: Path) -> None:
    reranker = BgeRerankerV2M3(
        model_dir=tmp_path,
        backend="onnx",
        batch_size=2,
        max_length=512,
    )

    reranker.load()

    assert reranker.status.loaded is False
    assert reranker.status.error == "model_files_missing"


async def test_reranker_rejects_inference_before_load(tmp_path: Path) -> None:
    reranker = BgeRerankerV2M3(
        model_dir=tmp_path,
        backend="onnx",
        batch_size=2,
        max_length=512,
    )

    with pytest.raises(RetrievalUnavailableError):
        await reranker.rerank("consulta", ("documento",))


async def test_reranker_handles_empty_documents_before_loading(tmp_path: Path) -> None:
    reranker = BgeRerankerV2M3(
        model_dir=tmp_path,
        backend="onnx",
        batch_size=2,
        max_length=512,
    )

    assert await reranker.rerank("consulta", ()) == ()
    with pytest.raises(ValueError):
        await reranker.rerank(" ", ("documento",))
