from pathlib import Path
from typing import NoReturn

BGE_M3_MODEL_ID = "BAAI/bge-m3"
BGE_RERANKER_MODEL_ID = "BAAI/bge-reranker-v2-m3"
BGE_M3_DIMENSION = 1024
BGE_M3_MAX_LENGTH = 8192
ONNX_INT8_FILE = "model_int8.onnx"
ONNX_FLOAT_FILE = "model.onnx"
TOKENIZER_FILE = "tokenizer.json"
SPARSE_WEIGHT_FILE = "sparse_linear.npy"
SPARSE_BIAS_FILE = "sparse_bias.npy"


class LocalModelError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def raise_model_error(code: str) -> NoReturn:
    raise LocalModelError(code)


def model_error_code(error: BaseException) -> str:
    if isinstance(error, LocalModelError):
        return error.code
    return "model_load_failed"


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise_model_error("model_files_missing")
    return path


def resolve_onnx_model(directory: Path) -> Path:
    for name in (ONNX_INT8_FILE, ONNX_FLOAT_FILE):
        candidate = directory / name
        if candidate.is_file():
            return candidate
    raise_model_error("model_files_missing")
