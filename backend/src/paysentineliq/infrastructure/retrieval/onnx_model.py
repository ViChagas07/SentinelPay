from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from paysentineliq.infrastructure.retrieval.errors import (
    LocalModelError,
    model_error_code,
    raise_model_error,
    require_file,
)


class OnnxTextModel:
    def __init__(
        self,
        model_path: Path,
        *,
        expected_rank: int,
        preferred_names: tuple[str, ...] = (),
    ) -> None:
        if expected_rank <= 0:
            raise ValueError("expected_rank must be positive")
        self._model_path = model_path
        self._expected_rank = expected_rank
        self._preferred_names = frozenset(preferred_names)
        self._session: Any | None = None
        self._input_names: frozenset[str] = frozenset()
        self._output_name = ""
        self._error: str | None = "not_loaded"

    @property
    def loaded(self) -> bool:
        return self._session is not None

    @property
    def error(self) -> str | None:
        return self._error

    def load(self) -> None:
        if self._session is not None:
            return
        try:
            require_file(self._model_path)
            try:
                import onnxruntime as ort
            except ImportError:
                raise_model_error("onnxruntime_unavailable")
            options = ort.SessionOptions()
            options.intra_op_num_threads = 0
            options.inter_op_num_threads = 1
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            session = ort.InferenceSession(
                str(self._model_path),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            inputs = session.get_inputs()
            names = frozenset(item.name for item in inputs)
            if "input_ids" not in names or "attention_mask" not in names:
                raise_model_error("model_input_invalid")
            outputs = session.get_outputs()
            if not outputs:
                raise_model_error("model_output_invalid")
            preferred = [output for output in outputs if output.name in self._preferred_names]
            candidates = [output for output in outputs if len(output.shape) == self._expected_rank]
            if preferred:
                selected = preferred[0]
            elif candidates:
                selected = candidates[0]
            else:
                selected = outputs[0]
            self._session = session
            self._input_names = names
            self._output_name = selected.name
            self._error = None
        except Exception as exc:
            self._error = model_error_code(exc)

    def run(
        self,
        input_ids: npt.NDArray[np.int64],
        attention_mask: npt.NDArray[np.int64],
    ) -> npt.NDArray[np.float32]:
        if self._session is None:
            raise LocalModelError(self._error or "model_load_failed")
        feed: dict[str, npt.NDArray[np.int64]] = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if "token_type_ids" in self._input_names:
            feed["token_type_ids"] = np.zeros_like(input_ids)
        try:
            outputs: list[object] = self._session.run([self._output_name], feed)
        except Exception as exc:
            raise LocalModelError("model_inference_failed") from exc
        if not outputs:
            raise_model_error("model_output_invalid")
        result: npt.NDArray[np.float32] = np.asarray(outputs[0], dtype=np.float32)
        return result

    def close(self) -> None:
        self._session = None
