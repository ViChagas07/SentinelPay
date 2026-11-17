import json
from pathlib import Path

import numpy as np
import numpy.typing as npt

from paysentineliq.infrastructure.retrieval.errors import (
    LocalModelError,
    raise_model_error,
    require_file,
)


class TextTokenizer:
    def __init__(self, tokenizer_file: Path, *, max_length: int) -> None:
        if max_length <= 0:
            raise ValueError("max_length must be positive")
        require_file(tokenizer_file)
        try:
            from tokenizers import Tokenizer
        except ImportError:
            raise_model_error("tokenizer_unavailable")
        try:
            tokenizer = Tokenizer.from_file(str(tokenizer_file))
            tokenizer.enable_truncation(max_length=max_length)
        except Exception as exc:
            raise LocalModelError("model_load_failed") from exc
        self._tokenizer = tokenizer
        self._pad_id = _resolve_pad_id(tokenizer_file, tokenizer)

    def encode_texts(
        self,
        texts: tuple[str, ...],
    ) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64]]:
        encodings = self._tokenizer.encode_batch(list(texts))
        return _stack_encodings([encoding.ids for encoding in encodings], self._pad_id)

    def encode_pairs(
        self,
        query: str,
        documents: tuple[str, ...],
    ) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64]]:
        encodings = [self._tokenizer.encode(query, document) for document in documents]
        return _stack_encodings([encoding.ids for encoding in encodings], self._pad_id)


def _resolve_pad_id(tokenizer_file: Path, tokenizer: object) -> int:
    config_path = tokenizer_file.with_name("tokenizer_config.json")
    pad_token_id: int | None = None
    if config_path.is_file():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise LocalModelError("model_load_failed") from exc
        if isinstance(raw, dict):
            pad_token = raw.get("pad_token")
            if isinstance(pad_token, str):
                pad_token_id = _token_id(tokenizer, pad_token)
            configured = raw.get("pad_token_id")
            if pad_token_id is None and isinstance(configured, int):
                pad_token_id = configured
    if pad_token_id is None:
        pad_token_id = _token_id(tokenizer, "<pad>")
    if pad_token_id is None:
        raise_model_error("model_load_failed")
    if pad_token_id < 0:
        raise_model_error("model_load_failed")
    return pad_token_id


def _token_id(tokenizer: object, token: str) -> int | None:
    lookup = getattr(tokenizer, "token_to_id", None)
    if not callable(lookup):
        return None
    token_id = lookup(token)
    return token_id if isinstance(token_id, int) else None


def _stack_encodings(
    sequences: list[list[int]],
    pad_id: int,
) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64]]:
    if not sequences:
        empty = np.zeros((0, 0), dtype=np.int64)
        return empty, empty.copy()
    width = max(len(sequence) for sequence in sequences)
    input_ids = np.full((len(sequences), width), pad_id, dtype=np.int64)
    attention_mask = np.zeros((len(sequences), width), dtype=np.int64)
    for row, sequence in enumerate(sequences):
        length = len(sequence)
        input_ids[row, :length] = sequence
        attention_mask[row, :length] = 1
    return input_ids, attention_mask
