import asyncio
import logging
from collections.abc import Sequence
from math import exp, isfinite
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

from paysentineliq.application.errors import RetrievalUnavailableError
from paysentineliq.domain.ports.retrieval import ModelStatus, RerankResult
from paysentineliq.infrastructure.retrieval.batching import iter_batches
from paysentineliq.infrastructure.retrieval.errors import (
    BGE_RERANKER_MODEL_ID,
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


def sigmoid(value: float) -> float:
    if not isfinite(value):
        raise ValueError("logit must be finite")
    if value >= 0.0:
        return 1.0 / (1.0 + exp(-value))
    factor = exp(value)
    return factor / (1.0 + factor)


def rank_scores(
    scores: Sequence[float],
    top_n: int | None,
) -> tuple[RerankResult, ...]:
    if top_n is not None and top_n <= 0:
        raise ValueError("top_n must be positive")
    if not scores:
        return ()
    indexed = sorted(enumerate(scores), key=lambda item: (-item[1], item[0]))
    selected = indexed if top_n is None else indexed[:top_n]
    return tuple(RerankResult(index=index, score=float(score)) for index, score in selected)


class BgeRerankerV2M3:
    def __init__(
        self,
        *,
        model_dir: Path,
        backend: Backend,
        batch_size: int,
        max_length: int,
        torch_num_threads: int = 0,
    ) -> None:
        if backend not in ("onnx", "pytorch"):
            raise ValueError("backend must be onnx or pytorch")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if max_length <= 0:
            raise ValueError("max_length must be positive")
        if torch_num_threads < 0:
            raise ValueError("torch_num_threads must be non-negative")
        self._model_dir = model_dir
        self._backend = backend
        self._batch_size = batch_size
        self._max_length = max_length
        self._torch_num_threads = torch_num_threads
        self._tokenizer: TextTokenizer | None = None
        self._onnx: OnnxTextModel | None = None
        self._torch_tokenizer: Any | None = None
        self._torch_model: Any | None = None
        self._error: str | None = "not_loaded"
        self._load_attempted = False

    @property
    def model_id(self) -> str:
        return BGE_RERANKER_MODEL_ID

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def status(self) -> ModelStatus:
        loaded = self._loaded
        return ModelStatus(
            model_id=BGE_RERANKER_MODEL_ID,
            backend=self._backend,
            loaded=loaded,
            error=None if loaded else self._error or "not_loaded",
        )

    def load(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        try:
            if self._backend == "onnx":
                self._load_onnx()
            else:
                self._load_pytorch()
            self._error = None
        except Exception as exc:
            self._error = model_error_code(exc)
            _logger.error("retrieval_reranker_load_failed code=%s", self._error)

    async def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]:
        if not query.strip():
            raise ValueError("query is required")
        if top_n is not None and top_n <= 0:
            raise ValueError("top_n must be positive")
        if not documents:
            return ()
        self._require_loaded()
        scores = await asyncio.to_thread(self._score_documents, query, documents)
        return rank_scores(scores, top_n)

    async def aclose(self) -> None:
        if self._onnx is not None:
            self._onnx.close()
        self._onnx = None
        self._torch_model = None
        self._torch_tokenizer = None
        self._tokenizer = None

    @property
    def _loaded(self) -> bool:
        if self._backend == "onnx":
            return self._onnx is not None and self._onnx.loaded
        return self._torch_model is not None

    def _require_loaded(self) -> None:
        if not self._loaded:
            raise RetrievalUnavailableError(self._error or "model_load_failed")

    def _load_onnx(self) -> None:
        model_path = resolve_onnx_model(self._model_dir)
        tokenizer = TextTokenizer(
            require_file(self._model_dir / TOKENIZER_FILE),
            max_length=self._max_length,
        )
        session = OnnxTextModel(model_path, expected_rank=2, preferred_names=("logits",))
        session.load()
        if not session.loaded:
            raise LocalModelError(session.error or "model_load_failed")
        self._tokenizer = tokenizer
        self._onnx = session

    def _load_pytorch(self) -> None:
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise LocalModelError("pytorch_unavailable") from exc
        try:
            if self._torch_num_threads > 0:
                torch.set_num_threads(self._torch_num_threads)
            tokenizer = AutoTokenizer.from_pretrained(
                str(self._model_dir),
                local_files_only=True,
            )
            model = AutoModelForSequenceClassification.from_pretrained(
                str(self._model_dir),
                local_files_only=True,
            )
            model.eval()
        except Exception as exc:
            raise LocalModelError("model_load_failed") from exc
        self._torch_tokenizer = tokenizer
        self._torch_model = model

    def _score_documents(
        self,
        query: str,
        documents: tuple[str, ...],
    ) -> tuple[float, ...]:
        scores: list[float] = []
        for batch in iter_batches(documents, self._batch_size):
            logits = self._forward(query, batch)
            if logits.ndim != 2 or logits.shape[1] != 1:
                raise LocalModelError("model_output_invalid")
            if logits.shape[0] != len(batch):
                raise LocalModelError("model_output_invalid")
            scores.extend(sigmoid(float(value)) for value in logits[:, 0])
        return tuple(scores)

    def _forward(
        self,
        query: str,
        batch: tuple[str, ...],
    ) -> npt.NDArray[np.float32]:
        if self._backend == "onnx":
            return self._forward_onnx(query, batch)
        return self._forward_pytorch(query, batch)

    def _forward_onnx(
        self,
        query: str,
        batch: tuple[str, ...],
    ) -> npt.NDArray[np.float32]:
        if self._onnx is None or self._tokenizer is None:
            raise RetrievalUnavailableError(self._error or "model_load_failed")
        input_ids, attention_mask = self._tokenizer.encode_pairs(query, batch)
        return self._onnx.run(input_ids, attention_mask)

    def _forward_pytorch(
        self,
        query: str,
        batch: tuple[str, ...],
    ) -> npt.NDArray[np.float32]:
        if self._torch_model is None or self._torch_tokenizer is None:
            raise RetrievalUnavailableError(self._error or "model_load_failed")
        import torch

        encoded = self._torch_tokenizer(
            [query] * len(batch),
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
        logits = getattr(output, "logits", None)
        if logits is None:
            logits = output[0]
        values: npt.NDArray[np.float32] = (
            logits.detach()
            .cpu()
            .numpy()
            .astype(
                np.float32,
            )
        )
        return values
