from pathlib import Path

import numpy as np
import pytest

from paysentineliq.application.errors import RetrievalUnavailableError
from paysentineliq.infrastructure.retrieval.bge_m3 import (
    BgeM3Embedder,
    dense_vector,
    sparse_scores,
    sparse_vector,
)

pytestmark = pytest.mark.unit


def test_dense_vector_normalizes_cls_token() -> None:
    hidden = np.zeros(1024, dtype=np.float32)
    hidden[0] = 3.0
    hidden[1] = 4.0

    vector = dense_vector(hidden)

    assert len(vector) == 1024
    assert vector[0] == pytest.approx(0.6)
    assert vector[1] == pytest.approx(0.8)
    assert sum(value * value for value in vector) == pytest.approx(1.0)


def test_dense_vector_rejects_wrong_dimension() -> None:
    with pytest.raises(ValueError):
        dense_vector(np.zeros(8, dtype=np.float32))


def test_sparse_vector_keeps_maximum_weight_per_token() -> None:
    vector = sparse_vector(
        token_ids=[5, 5, 7, 9],
        scores=[0.2, 0.4, 0.0, 1.0],
    )

    assert vector.as_dict()[5] == pytest.approx(0.4)
    assert vector.as_dict()[9] == 1.0
    assert set(vector.as_dict()) == {5, 9}


def test_sparse_vector_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError):
        sparse_vector(token_ids=[1, 2], scores=[0.5])


def test_sparse_scores_applies_bias_and_attention_mask() -> None:
    hidden = np.full((2, 1024), 0.5, dtype=np.float32)
    mask = np.asarray([1, 0], dtype=np.int64)
    weight = np.ones(1024, dtype=np.float32)

    scores = sparse_scores(hidden, mask, weight, 0.1)

    assert scores[0] == pytest.approx(512.1)
    assert scores[1] == pytest.approx(0.0)


def test_embedder_reports_missing_files_without_raising(tmp_path: Path) -> None:
    embedder = BgeM3Embedder(
        model_dir=tmp_path,
        backend="onnx",
        batch_size=2,
    )

    embedder.load()

    assert embedder.status.loaded is False
    assert embedder.status.error == "model_files_missing"
    assert embedder.sparse_status.loaded is False


async def test_embedder_rejects_inference_before_load(tmp_path: Path) -> None:
    embedder = BgeM3Embedder(
        model_dir=tmp_path,
        backend="onnx",
        batch_size=2,
    )

    with pytest.raises(RetrievalUnavailableError):
        await embedder.embed(("texto",))


def test_embedder_rejects_invalid_settings(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        BgeM3Embedder(model_dir=tmp_path, backend="onnx", batch_size=0)
    with pytest.raises(ValueError):
        BgeM3Embedder(model_dir=tmp_path, backend="onnx", batch_size=1, max_length=0)
