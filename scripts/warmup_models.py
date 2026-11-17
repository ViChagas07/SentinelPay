import argparse
import importlib.util
import os
import shutil
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from paysentineliq.infrastructure.retrieval.errors import (  # noqa: E402
    BGE_M3_DIMENSION,
    BGE_M3_MODEL_ID,
    BGE_RERANKER_MODEL_ID,
    SPARSE_BIAS_FILE,
    SPARSE_WEIGHT_FILE,
)

_EMBEDDER_DIR = "bge-m3"
_RERANKER_DIR = "bge-reranker-v2-m3"
_TOKENIZER_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "sentencepiece.bpe.model",
)
_EMBEDDER_ONNX_FILES = (
    "onnx/model.onnx",
    "onnx/model.onnx_data",
    "onnx/config.json",
    "onnx/tokenizer.json",
    "onnx/tokenizer_config.json",
    "onnx/special_tokens_map.json",
    "onnx/sentencepiece.bpe.model",
    "sparse_linear.pt",
)
_EMBEDDER_PYTORCH_FILES = (
    "config.json",
    "pytorch_model.bin",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "sentencepiece.bpe.model",
    "sparse_linear.pt",
)
_RERANKER_FILES = (
    "config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "sentencepiece.bpe.model",
)


class WarmupError(RuntimeError):
    pass


class _ClassifierOutput(Protocol):
    logits: object


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _require_module(name: str, purpose: str) -> None:
    if not _has_module(name):
        raise WarmupError(f"{purpose} requer o pacote {name}; instale antes de rodar o warmup")


def _download(repo_id: str, patterns: Sequence[str]) -> Path:
    _require_module("huggingface_hub", "download do modelo")
    from huggingface_hub import snapshot_download

    try:
        snapshot = snapshot_download(repo_id=repo_id, allow_patterns=list(patterns))
    except Exception as exc:
        raise WarmupError(f"falha ao baixar {repo_id}: {exc}") from exc
    return Path(snapshot)


def _copy_files(snapshot: Path, target: Path, names: Sequence[str]) -> None:
    copied = 0
    for name in names:
        source = snapshot / name
        if not source.is_file():
            continue
        destination = target / Path(name).name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        copied += 1
    if copied == 0:
        raise WarmupError(f"nenhum arquivo esperado foi encontrado em {snapshot}")


def _extract_sparse_weights(sparse_file: Path, target: Path) -> None:
    if not sparse_file.is_file():
        raise WarmupError("sparse_linear.pt nao encontrado no snapshot do BGE-M3")
    try:
        with zipfile.ZipFile(sparse_file) as archive:
            names = set(archive.namelist())
            weight_name = "sparse_linear/data/0"
            if weight_name not in names:
                raise WarmupError("formato inesperado de sparse_linear.pt")
            byteorder = "little"
            if "sparse_linear/byteorder" in names:
                byteorder = archive.read("sparse_linear/byteorder").decode().strip()
            dtype = "<f2" if byteorder == "little" else ">f2"
            weight = np.frombuffer(archive.read(weight_name), dtype=dtype).astype(np.float32)
            bias = 0.0
            bias_name = "sparse_linear/data/1"
            if bias_name in names:
                raw_bias = archive.read(bias_name)
                if len(raw_bias) >= 2:
                    bias = float(np.frombuffer(raw_bias, dtype=dtype)[0])
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise WarmupError(f"falha ao ler sparse_linear.pt: {exc}") from exc
    if weight.size != BGE_M3_DIMENSION:
        raise WarmupError(
            f"peso esparso com dimensao inesperada: {weight.size} em vez de {BGE_M3_DIMENSION}",
        )
    np.save(target / SPARSE_WEIGHT_FILE, weight)
    np.save(target / SPARSE_BIAS_FILE, np.asarray(bias, dtype=np.float32))


def _quantize_onnx(source: Path, destination: Path) -> None:
    _require_module("onnx", "quantizacao int8")
    _require_module("onnxruntime", "quantizacao int8")
    from onnxruntime.quantization import QuantType, quantize_dynamic

    if not source.is_file():
        raise WarmupError(f"modelo ONNX ausente: {source}")
    try:
        quantize_dynamic(
            model_input=str(source),
            model_output=str(destination),
            weight_type=QuantType.QInt8,
        )
    except Exception as exc:
        raise WarmupError(f"falha ao quantizar {source.name}: {exc}") from exc
    if not destination.is_file():
        raise WarmupError("a quantizacao nao gerou o arquivo de saida")


def _export_reranker(snapshot: Path, destination: Path, *, max_length: int) -> None:
    _require_module("torch", "exportacao ONNX do reranker")
    _require_module("transformers", "exportacao ONNX do reranker")
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(snapshot),
        local_files_only=True,
    )
    model.eval()
    encoded = tokenizer(
        "consulta",
        "documento",
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=max_length,
    )

    def _forward(input_ids: object, attention_mask: object) -> object:
        output: _ClassifierOutput = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )
        return output.logits

    try:
        torch.onnx.export(
            _forward,
            (encoded["input_ids"], encoded["attention_mask"]),
            str(destination),
            input_names=["input_ids", "attention_mask"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "sequence"},
                "attention_mask": {0: "batch", 1: "sequence"},
                "logits": {0: "batch"},
            },
            opset_version=17,
            do_constant_folding=True,
        )
    except Exception as exc:
        raise WarmupError(f"falha ao exportar o reranker para ONNX: {exc}") from exc


def _prepare_embedder(output_dir: Path, backend: str, *, force: bool) -> None:
    target = output_dir / _EMBEDDER_DIR
    target.mkdir(parents=True, exist_ok=True)
    if backend == "onnx":
        existing = target / "model_int8.onnx"
        if existing.is_file() and not force:
            print(f"embedder ONNX ja existe em {target}; nada a fazer")
            return
        snapshot = _download(BGE_M3_MODEL_ID, _EMBEDDER_ONNX_FILES)
        _copy_files(snapshot / "onnx", target, _TOKENIZER_FILES)
        _copy_files(snapshot / "onnx", target, ("config.json",))
        _quantize_onnx(snapshot / "onnx" / "model.onnx", target / "model_int8.onnx")
    else:
        existing = target / "pytorch_model.bin"
        if existing.is_file() and not force:
            print(f"embedder PyTorch ja existe em {target}; nada a fazer")
            return
        snapshot = _download(BGE_M3_MODEL_ID, _EMBEDDER_PYTORCH_FILES)
        _copy_files(
            snapshot,
            target,
            ("config.json", "pytorch_model.bin", *_TOKENIZER_FILES),
        )
    _extract_sparse_weights(snapshot / "sparse_linear.pt", target)
    print(f"embedder preparado em {target}")


def _prepare_reranker(
    output_dir: Path,
    backend: str,
    *,
    force: bool,
    max_length: int,
) -> None:
    target = output_dir / _RERANKER_DIR
    target.mkdir(parents=True, exist_ok=True)
    if backend == "onnx":
        existing = target / "model_int8.onnx"
        if existing.is_file() and not force:
            print(f"reranker ONNX ja existe em {target}; nada a fazer")
            return
        snapshot = _download(BGE_RERANKER_MODEL_ID, _RERANKER_FILES)
        _copy_files(snapshot, target, _TOKENIZER_FILES)
        _copy_files(snapshot, target, ("config.json",))
        _export_reranker(snapshot, target / "model.onnx", max_length=max_length)
        _quantize_onnx(target / "model.onnx", target / "model_int8.onnx")
    else:
        existing = target / "model.safetensors"
        if existing.is_file() and not force:
            print(f"reranker PyTorch ja existe em {target}; nada a fazer")
            return
        snapshot = _download(BGE_RERANKER_MODEL_ID, _RERANKER_FILES)
        _copy_files(snapshot, target, ("config.json", "model.safetensors", *_TOKENIZER_FILES))
    print(f"reranker preparado em {target}")


def _dry_run(output_dir: Path, backend: str, skip_embedder: bool, skip_reranker: bool) -> None:
    print(f"destino: {output_dir}")
    print(f"backend: {backend}")
    if not skip_embedder:
        print(f"embedder: {BGE_M3_MODEL_ID} -> {output_dir / _EMBEDDER_DIR}")
    if not skip_reranker:
        print(f"reranker: {BGE_RERANKER_MODEL_ID} -> {output_dir / _RERANKER_DIR}")
    checks = [("numpy", True), ("huggingface_hub", True)]
    if backend in ("onnx", "both"):
        checks.extend((("onnxruntime", True), ("onnx", True)))
    if backend in ("onnx", "both") and not skip_reranker:
        checks.extend((("torch", False), ("transformers", False)))
    for module, required in checks:
        state = "ok" if _has_module(module) else "ausente"
        suffix = "" if required or _has_module(module) else " (necessario para exportar o reranker)"
        print(f"pacote {module}: {state}{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Baixa, converte e quantiza os modelos locais de retrieval do SentinelPay. "
            "Os binarios ficam fora do git, em models/retrieval por padrao."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("RETRIEVAL_MODEL_DIR", "models/retrieval")),
    )
    parser.add_argument("--backend", choices=("onnx", "pytorch", "both"), default="onnx")
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-embedder", action="store_true")
    parser.add_argument("--skip-reranker", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.max_length <= 0:
        parser.error("--max-length deve ser positivo")
    if args.skip_embedder and args.skip_reranker:
        parser.error("nada para fazer: embedder e reranker foram pulados")

    output_dir: Path = args.output_dir
    if args.dry_run:
        _dry_run(output_dir, args.backend, args.skip_embedder, args.skip_reranker)
        return 0

    try:
        embedder_backends = ("onnx", "pytorch") if args.backend == "both" else (args.backend,)
        if not args.skip_embedder:
            for backend in embedder_backends:
                _prepare_embedder(output_dir, backend, force=args.force)
        if not args.skip_reranker:
            for backend in embedder_backends:
                _prepare_reranker(
                    output_dir,
                    backend,
                    force=args.force,
                    max_length=args.max_length,
                )
    except WarmupError as exc:
        print(f"FALHA: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
