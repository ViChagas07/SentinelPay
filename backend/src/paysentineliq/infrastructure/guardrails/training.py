import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from paysentineliq.infrastructure.guardrails.synthetic import (
    InjectionDataset,
    normalize_sample,
)

_logger = logging.getLogger("paysentineliq")

DEFAULT_MODEL_VERSION = "guardrail-injection-v1"
DEFAULT_REGISTRY_NAME = "guardrail-injection-v1.json"
COVERAGE_LABEL = "limited"
_MAX_SCORE_CHARS = 20_000


class GuardrailArtifactError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    model_version: str = DEFAULT_MODEL_VERSION
    seed: int = 42
    test_fraction: float = 0.25
    threshold: float = 0.5

    def __post_init__(self) -> None:
        if not self.model_version.strip():
            raise ValueError("model_version is required")
        if "/" in self.model_version or "\\" in self.model_version:
            raise ValueError("model_version must not contain path separators")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if not 0.0 < self.test_fraction < 1.0:
            raise ValueError("test_fraction must be between 0 and 1")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class TrainingResult:
    artifact_path: Path
    registry_path: Path
    artifact_sha256: str
    dataset_hash: str
    metrics: dict[str, Any]
    model_version: str


@dataclass(frozen=True, slots=True)
class ArtifactInfo:
    model_version: str
    artifact_path: Path
    sha256: str
    dataset_hash: str
    dataset_description: str
    synthetic: bool
    coverage: str
    metrics: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_inside(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise GuardrailArtifactError("artifact path is outside the trusted directory")
    return candidate


def build_pipeline(seed: int) -> Any:
    return Pipeline(
        [
            (
                "vectorizer",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    min_df=1,
                    max_features=20_000,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=2_000,
                    class_weight="balanced",
                    random_state=seed,
                ),
            ),
        ],
    )


def train_injection_classifier(
    dataset: InjectionDataset,
    output_dir: Path,
    config: TrainingConfig | None = None,
) -> TrainingResult:
    actual = config if config is not None else TrainingConfig()
    texts = [normalize_sample(sample.text) for sample in dataset.samples]
    labels = np.asarray([sample.label for sample in dataset.samples], dtype=int)
    if len(np.unique(labels)) < 2:
        raise ValueError("training data needs two classes")

    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts,
        labels,
        test_size=actual.test_fraction,
        random_state=actual.seed,
        stratify=labels,
    )
    pipeline = build_pipeline(actual.seed)
    pipeline.fit(train_texts, train_labels)
    probabilities = np.asarray(pipeline.predict_proba(test_texts)[:, 1], dtype=float)
    predictions = (probabilities >= actual.threshold).astype(int)
    two_classes = len(np.unique(test_labels)) >= 2
    metrics: dict[str, Any] = {
        "synthetic": True,
        "coverage": COVERAGE_LABEL,
        "model_version": actual.model_version,
        "seed": actual.seed,
        "threshold": actual.threshold,
        "dataset_hash": dataset.hash,
        "dataset_description": dataset.description,
        "n_train": len(train_texts),
        "n_test": len(test_texts),
        "precision": float(precision_score(test_labels, predictions, zero_division=0)),
        "recall": float(recall_score(test_labels, predictions, zero_division=0)),
        "f1": float(f1_score(test_labels, predictions, zero_division=0)),
        "roc_auc": (float(roc_auc_score(test_labels, probabilities)) if two_classes else None),
        "note": "metricas sinteticas; nao representam ataques reais ou adaptativos",
    }

    output = output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifact_path = output / f"{actual.model_version}.joblib"
    payload = {
        "schema_version": 1,
        "model_version": actual.model_version,
        "pipeline": pipeline,
        "dataset_hash": dataset.hash,
        "dataset_description": dataset.description,
        "synthetic": True,
        "coverage": COVERAGE_LABEL,
    }
    joblib.dump(payload, artifact_path)
    digest = _sha256(artifact_path)

    registry_path = output / f"{actual.model_version}.json"
    registry = {
        "schema_version": 1,
        "model_version": actual.model_version,
        "artifact": artifact_path.name,
        "sha256": digest,
        "dataset_hash": dataset.hash,
        "dataset_description": dataset.description,
        "synthetic": True,
        "coverage": COVERAGE_LABEL,
        "metrics": metrics,
    }
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return TrainingResult(
        artifact_path=artifact_path,
        registry_path=registry_path,
        artifact_sha256=digest,
        dataset_hash=dataset.hash,
        metrics=metrics,
        model_version=actual.model_version,
    )


def load_registry(
    model_dir: Path,
    registry_name: str = DEFAULT_REGISTRY_NAME,
) -> ArtifactInfo:
    root = model_dir.resolve()
    registry_path = _resolve_inside(root, registry_name)
    if not registry_path.is_file():
        raise GuardrailArtifactError("guardrail registry not found")
    try:
        payload: object = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardrailArtifactError("invalid guardrail registry") from exc
    if not isinstance(payload, dict):
        raise GuardrailArtifactError("invalid guardrail registry")

    model_version = payload.get("model_version")
    artifact_name = payload.get("artifact")
    expected_hash = payload.get("sha256")
    dataset_hash = payload.get("dataset_hash")
    dataset_description = payload.get("dataset_description")
    synthetic = payload.get("synthetic")
    coverage = payload.get("coverage")
    metrics = payload.get("metrics")
    if not isinstance(model_version, str) or not model_version.strip():
        raise GuardrailArtifactError("model_version is required")
    if not isinstance(artifact_name, str) or not artifact_name.strip():
        raise GuardrailArtifactError("artifact is required")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise GuardrailArtifactError("sha256 is required")
    if not isinstance(dataset_hash, str) or not dataset_hash.strip():
        raise GuardrailArtifactError("dataset_hash is required")
    if not isinstance(dataset_description, str):
        raise GuardrailArtifactError("dataset_description is required")
    if synthetic is not True:
        raise GuardrailArtifactError("guardrail model must be synthetic")
    if coverage != COVERAGE_LABEL:
        raise GuardrailArtifactError("guardrail model must declare limited coverage")
    if not isinstance(metrics, dict):
        raise GuardrailArtifactError("metrics are required")

    artifact_path = _resolve_inside(root, artifact_name)
    if not artifact_path.is_file():
        raise GuardrailArtifactError("guardrail artifact not found")
    actual_hash = _sha256(artifact_path)
    if not hmac.compare_digest(actual_hash, expected_hash):
        raise GuardrailArtifactError("guardrail artifact hash mismatch")
    return ArtifactInfo(
        model_version=model_version,
        artifact_path=artifact_path,
        sha256=actual_hash,
        dataset_hash=dataset_hash,
        dataset_description=dataset_description,
        synthetic=True,
        coverage=coverage,
        metrics=dict(metrics),
    )


class SklearnInjectionClassifier:
    def __init__(self, info: ArtifactInfo) -> None:
        try:
            payload: object = joblib.load(info.artifact_path)
        except Exception as exc:
            raise GuardrailArtifactError("cannot load guardrail artifact") from exc
        if not isinstance(payload, dict):
            raise GuardrailArtifactError("invalid guardrail artifact")
        if payload.get("model_version") != info.model_version:
            raise GuardrailArtifactError("guardrail artifact version mismatch")
        pipeline: Any | None = payload.get("pipeline")
        if pipeline is None:
            raise GuardrailArtifactError("guardrail pipeline is missing")
        self._pipeline: Any = pipeline
        self._info = info

    @classmethod
    def from_directory(cls, model_dir: Path) -> "SklearnInjectionClassifier":
        return cls(load_registry(model_dir))

    @property
    def available(self) -> bool:
        return True

    @property
    def model_version(self) -> str:
        return self._info.model_version

    @property
    def coverage(self) -> str:
        return self._info.coverage

    def score(self, text: str) -> float:
        normalized = normalize_sample(text)[:_MAX_SCORE_CHARS]
        matrix = np.asarray([normalized], dtype=object)
        probability = float(self._pipeline.predict_proba(matrix)[0, 1])
        return max(0.0, min(1.0, probability))


def load_injection_classifier(model_dir: Path) -> SklearnInjectionClassifier:
    return SklearnInjectionClassifier.from_directory(model_dir)


def load_injection_classifier_or_none(
    model_dir: Path,
) -> SklearnInjectionClassifier | None:
    try:
        return load_injection_classifier(model_dir)
    except Exception:
        _logger.error("guardrail_classifier_unavailable")
        return None
