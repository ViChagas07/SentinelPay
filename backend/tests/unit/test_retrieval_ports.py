import pytest

from paysentineliq.domain.ports.retrieval import (
    ModelStatus,
    RerankResult,
    RetrievalStatus,
    SparseVector,
)

pytestmark = pytest.mark.unit


def test_sparse_vector_requires_ordered_unique_tokens() -> None:
    vector = SparseVector(((1, 0.5), (3, 1.5)))

    assert vector.as_dict() == {1: 0.5, 3: 1.5}
    with pytest.raises(ValueError):
        SparseVector(((3, 0.5), (1, 1.5)))
    with pytest.raises(ValueError):
        SparseVector(((1, 0.5), (1, 1.0)))


def test_sparse_vector_rejects_non_positive_weights() -> None:
    with pytest.raises(ValueError):
        SparseVector(((1, 0.0),))
    with pytest.raises(ValueError):
        SparseVector(((1, -0.1),))


def test_rerank_result_rejects_invalid_scores() -> None:
    assert RerankResult(index=0, score=0.5).score == 0.5
    with pytest.raises(ValueError):
        RerankResult(index=-1, score=0.5)
    with pytest.raises(ValueError):
        RerankResult(index=0, score=1.5)


def test_model_status_rejects_error_on_loaded_model() -> None:
    status = ModelStatus(
        model_id="BAAI/bge-m3",
        backend="onnx",
        loaded=False,
        error="model_files_missing",
    )

    assert status.error == "model_files_missing"
    with pytest.raises(ValueError):
        ModelStatus(
            model_id="BAAI/bge-m3",
            backend="onnx",
            loaded=True,
            error="model_files_missing",
        )


def test_retrieval_status_requires_consistent_reranker() -> None:
    embedder = ModelStatus("BAAI/bge-m3", "onnx", True)
    reranker = ModelStatus("BAAI/bge-reranker-v2-m3", "onnx", True)

    status = RetrievalStatus(
        top_k=25,
        rerank_top_n=4,
        rerank_enabled=True,
        embedder=embedder,
        sparse_embedder=embedder,
        reranker=reranker,
    )

    assert status.reranker == reranker
    with pytest.raises(ValueError):
        RetrievalStatus(
            top_k=25,
            rerank_top_n=30,
            rerank_enabled=True,
            embedder=embedder,
            sparse_embedder=embedder,
            reranker=reranker,
        )
    with pytest.raises(ValueError):
        RetrievalStatus(
            top_k=25,
            rerank_top_n=4,
            rerank_enabled=False,
            embedder=embedder,
            sparse_embedder=embedder,
            reranker=reranker,
        )
