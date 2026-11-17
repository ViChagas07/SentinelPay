import asyncio
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

from paysentineliq.application.errors import RetrievalUnavailableError
from paysentineliq.domain.ports.retrieval import ModelStatus, SparseVector
from paysentineliq.infrastructure.retrieval.batching import iter_batches
from paysentineliq.infrastructure.retrieval.errors import (
    BGE_M3_DIMENSION,
    BGE_M3_MAX_LENGTH,
    BGE_M3_MODEL_ID,
    SPARSE_BIAS_FILE,
    SPARSE_WEIGHT_FILE,
    TOKENIZER_FILE,
    LocalModelError,
    model_error_code,
    require_file,
    resolve_onnx_model,
)
from paysentineliq.infrastructure.retrieval.onnx_model import OnnxTextModel
from paysentineliq.infrastructure.retrieval.text import TextTokenizer

_logger = logging.getLogger("paysentineliq")

Backend = Literal["onnx", "pytorch"]


def dense_vector(hidden_row: npt.NDArray[np.float32]) -> tuple[float, ...]:
    values = np.asarray(hidden_row, dtype=np.float32).reshape(-1)
    if values.size != BGE_M3_DIMENSION:
        raise ValueError("dense hidden state has the wrong dimension")
    norm = float(np.linalg.norm(values))
    if norm == 0.0:
        return tuple(0.0 for _ in values)
    return tuple(float(value / norm) for value in values)


def sparse_scores(
    hidden: npt.NDArray[np.float32],
    attention_mask: npt.NDArray[np.int64],
    weight: npt.NDArray[np.float32],
    bias: float,
) -> npt.NDArray[np.float32]:
    values = np.asarray(hidden, dtype=np.float32)
    if values.ndim != 2 or values.shape[1] != weight.shape[0]:
        raise ValueError("sparse hidden state has the wrong shape")
    if attention_mask.shape != (values.shape[0],):
        raise ValueError("attention mask has the wrong shape")
    raw = values @ weight + bias
    masked: npt.NDArray[np.float32] = np.maximum(raw, 0.0) * attention_mask.astype(
        np.float32,
    )
    return masked


def sparse_vector(
    token_ids: Sequence[int],
    scores: Sequence[float],
) -> SparseVector:
    if len(token_ids) != len(scores):
        raise ValueError("token ids and scores must have the same length")
    aggregated: dict[int, float] = {}
    for token_id, score in zip(token_ids, scores, strict=True):
        if token_id < 0:
            raise ValueError("token id must be non-negative")
        value = float(score)
        if value <= 0.0 or not np.isfinite(value):
            continue
        current = aggregated.get(token_id)
        if current is None or value > current:
            aggregated[token_id] = value
    return SparseVector(tuple(sorted(aggregated.items())))


class BgeM3Embedder:
    def __init__(
        self,
        *,
        model_dir: Path,
        backend: Backend,
        batch_size: int,
        torch_num_threads: int = 0,
        max_length: int = BGE_M3_MAX_LENGTH,
    ) -> None:
        if backend not in ("onnx", "pytorch"):
            raise ValueError("backend must be onnx or pytorch")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if torch_num_threads < 0:
            raise ValueError("torch_num_threads must be non-negative")
        if max_length <= 0:
            raise ValueError("max_length must be positive")
        self._model_dir = model_dir
        self._backend = backend
        self._batch_size = batch_size
        self._torch_num_threads = torch_num_threads
        self._max_length = max_length
        self._tokenizer: TextTokenizer | None = None
        self._onnx: OnnxTextModel | None = None
        self._torch_tokenizer: Any | None = None
        self._torch_model: Any | None = None
        self._sparse_weight: npt.NDArray[np.float32] | None = None
        self._sparse_bias = 0.0
        self._dense_error: str | None = "not_loaded"
        self._sparse_error: str | None = "not_loaded"
        self._load_attempted = False

    @property
    def dimension(self) -> int:
        return BGE_M3_DIMENSION

    @property
    def model_id(self) -> str:
        return BGE_M3_MODEL_ID

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def status(self) -> ModelStatus:
        loaded = self._encoder_loaded
        return ModelStatus(
            model_id=BGE_M3_MODEL_ID,
            backend=self._backend,
            loaded=loaded,
            error=None if loaded else self._dense_error or "not_loaded",
        )

    @property
    def sparse_status(self) -> ModelStatus:
        loaded = self._encoder_loaded and self._sparse_weight is not None
        error = None
        if not loaded:
            error = self._dense_error or self._sparse_error or "not_loaded"
        return ModelStatus(
            model_id=BGE_M3_MODEL_ID,
            backend=self._backend,
            loaded=loaded,
            error=error,
        )

    def load(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        try:
            self._load_encoder()
            self._dense_error = None
        except Exception as exc:
            self._dense_error = model_error_code(exc)
            _logger.error("retrieval_embedder_load_failed code=%s", self._dense_error)
        try:
            self._load_sparse_weights()
            self._sparse_error = None
        except Exception as exc:
            self._sparse_error = model_error_code(exc)
            _logger.error("retrieval_sparse_load_failed code=%s", self._sparse_error)

    async def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        self._require_encoder()
        return await asyncio.to_thread(self._embed_dense, texts)

    async def embed_sparse(self, texts: tuple[str, ...]) -> tuple[SparseVector, ...]:
        if not texts:
            return ()
        self._require_encoder()
        if self._sparse_weight is None:
            raise RetrievalUnavailableError(self._sparse_error or "model_load_failed")
        return await asyncio.to_thread(self._embed_sparse, texts)

    async def embed_hybrid(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[tuple[float, ...], ...], tuple[SparseVector, ...]]:
        if not texts:
            return (), ()
        self._require_encoder()
        if self._sparse_weight is None:
            raise RetrievalUnavailableError(self._sparse_error or "model_load_failed")
        return await asyncio.to_thread(self._embed_both, texts)

    async def aclose(self) -> None:
        if self._onnx is not None:
            self._onnx.close()
        self._onnx = None
        self._torch_model = None
        self._torch_tokenizer = None
        self._tokenizer = None

    @property
    def _encoder_loaded(self) -> bool:
        if self._backend == "onnx":
            return self._onnx is not None and self._onnx.loaded
        return self._torch_model is not None

    def _require_encoder(self) -> None:
        if not self._encoder_loaded:
            raise RetrievalUnavailableError(self._dense_error or "model_load_failed")

    def _load_encoder(self) -> None:
        if self._backend == "onnx":
            self._load_onnx_encoder()
        else:
            self._load_pytorch_encoder()

    def _load_onnx_encoder(self) -> None:
        model_path = resolve_onnx_model(self._model_dir)
        tokenizer = TextTokenizer(
            require_file(self._model_dir / TOKENIZER_FILE),
            max_length=self._max_length,
        )
        session = OnnxTextModel(
            model_path,
            expected_rank=3,
            preferred_names=("token_embeddings", "last_hidden_state"),
        )
        session.load()
        if not session.loaded:
            raise LocalModelError(session.error or "model_load_failed")
        self._tokenizer = tokenizer
        self._onnx = session

    def _load_pytorch_encoder(self) -> None:
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise LocalModelError("pytorch_unavailable") from exc
        try:
            if self._torch_num_threads > 0:
                torch.set_num_threads(self._torch_num_threads)
            tokenizer = AutoTokenizer.from_pretrained(
                str(self._model_dir),
                local_files_only=True,
            )
            model = AutoModel.from_pretrained(
                str(self._model_dir),
                local_files_only=True,
            )
            model.eval()
        except Exception as exc:
            raise LocalModelError("model_load_failed") from exc
        self._torch_tokenizer = tokenizer
        self._torch_model = model

    def _load_sparse_weights(self) -> None:
        weight = np.load(
            require_file(self._model_dir / SPARSE_WEIGHT_FILE),
            allow_pickle=False,
        )
        values = np.asarray(weight, dtype=np.float32).reshape(-1)
        if values.size != BGE_M3_DIMENSION or not np.all(np.isfinite(values)):
            raise LocalModelError("model_load_failed")
        bias_path = self._model_dir / SPARSE_BIAS_FILE
        bias = 0.0
        if bias_path.is_file():
            bias = float(
                np.asarray(
                    np.load(bias_path, allow_pickle=False),
                    dtype=np.float32,
                ).reshape(-1)[0],
            )
            if not np.isfinite(bias):
                raise LocalModelError("model_load_failed")
        self._sparse_weight = values
        self._sparse_bias = bias

    def _embed_dense(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        vectors: list[tuple[float, ...]] = []
        for batch in iter_batches(texts, self._batch_size):
            hidden, _, _ = self._forward(batch)
            for row in range(len(batch)):
                vectors.append(dense_vector(hidden[row, 0]))
        return tuple(vectors)

    def _embed_sparse(self, texts: tuple[str, ...]) -> tuple[SparseVector, ...]:
        vectors: list[SparseVector] = []
        for batch in iter_batches(texts, self._batch_size):
            hidden, input_ids, attention_mask = self._forward(batch)
            for row in range(len(batch)):
                scores = sparse_scores(
                    hidden[row],
                    attention_mask[row],
                    self._require_sparse_weight(),
                    self._sparse_bias,
                )
                vectors.append(sparse_vector(input_ids[row].tolist(), scores.tolist()))
        return tuple(vectors)

    def _embed_both(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[tuple[float, ...], ...], tuple[SparseVector, ...]]:
        dense: list[tuple[float, ...]] = []
        sparse: list[SparseVector] = []
        for batch in iter_batches(texts, self._batch_size):
            hidden, input_ids, attention_mask = self._forward(batch)
            for row in range(len(batch)):
                dense.append(dense_vector(hidden[row, 0]))
                scores = sparse_scores(
                    hidden[row],
                    attention_mask[row],
                    self._require_sparse_weight(),
                    self._sparse_bias,
                )
                sparse.append(sparse_vector(input_ids[row].tolist(), scores.tolist()))
        return tuple(dense), tuple(sparse)

    def _require_sparse_weight(self) -> npt.NDArray[np.float32]:
        if self._sparse_weight is None:
            raise RetrievalUnavailableError(self._sparse_error or "model_load_failed")
        return self._sparse_weight

    def _forward(
        self,
        batch: tuple[str, ...],
    ) -> tuple[
        npt.NDArray[np.float32],
        npt.NDArray[np.int64],
        npt.NDArray[np.int64],
    ]:
        if self._backend == "onnx":
            return self._forward_onnx(batch)
        return self._forward_pytorch(batch)

    def _forward_onnx(
        self,
        batch: tuple[str, ...],
    ) -> tuple[
        npt.NDArray[np.float32],
        npt.NDArray[np.int64],
        npt.NDArray[np.int64],
    ]:
        if self._onnx is None or self._tokenizer is None:
            raise RetrievalUnavailableError(self._dense_error or "model_load_failed")
        input_ids, attention_mask = self._tokenizer.encode_texts(batch)
        hidden = self._onnx.run(input_ids, attention_mask)
        if hidden.ndim != 3 or hidden.shape[2] != BGE_M3_DIMENSION:
            raise LocalModelError("model_output_invalid")
        if hidden.shape[0] != len(batch):
            raise LocalModelError("model_output_invalid")
        return hidden, input_ids, attention_mask

    def _forward_pytorch(
        self,
        batch: tuple[str, ...],
    ) -> tuple[
        npt.NDArray[np.float32],
        npt.NDArray[np.int64],
        npt.NDArray[np.int64],
    ]:
        if self._torch_model is None or self._torch_tokenizer is None:
            raise RetrievalUnavailableError(self._dense_error or "model_load_failed")
        import torch

        encoded = self._torch_tokenizer(
            list(batch),
            padding=True,
            truncation=True,
            max_length=self._max_length,
            return_tensors="pt",
        )
        input_ids = encoded["input_ids"]
        attention_mask = encoded["attention_mask"]
        with torch.inference_mode():
            output = self._torch_model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )
        hidden = getattr(output, "last_hidden_state", None)
        if hidden is None:
            hidden = output[0]
        hidden_array: npt.NDArray[np.float32] = hidden.detach().cpu().numpy().astype(np.float32)
        ids_array: npt.NDArray[np.int64] = input_ids.detach().cpu().numpy().astype(np.int64)
        mask_array: npt.NDArray[np.int64] = attention_mask.detach().cpu().numpy().astype(np.int64)
        if hidden_array.ndim != 3 or hidden_array.shape[2] != BGE_M3_DIMENSION:
            raise LocalModelError("model_output_invalid")
        return hidden_array, ids_array, mask_array
