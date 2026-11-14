import hashlib
import hmac
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from paysentineliq.application.ports.fraud_model import ModelPrediction
from paysentineliq.application.queries.fraud_features import FEATURE_NAMES

_logger = logging.getLogger("paysentineliq")

DEFAULT_REGISTRY_NAME = "fraud-risk-v1.json"


class ModelArtifactError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ArtifactInfo:
    model_version: str
    artifact_path: Path
    sha256: str
    dataset_hash: str
    dataset_description: str
    synthetic: bool
    feature_names: tuple[str, ...]
    metrics: Mapping[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_inside(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise ModelArtifactError("artifact path is outside the trusted directory")
    return candidate


def load_registry(
    model_dir: Path,
    registry_name: str = DEFAULT_REGISTRY_NAME,
) -> ArtifactInfo:
    root = model_dir.resolve()
    registry_path = _resolve_inside(root, registry_name)
    if not registry_path.is_file():
        raise ModelArtifactError("model registry not found")
    try:
        payload: object = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelArtifactError("invalid model registry") from exc
    if not isinstance(payload, dict):
        raise ModelArtifactError("invalid model registry")

    model_version = payload.get("model_version")
    artifact_name = payload.get("artifact")
    expected_hash = payload.get("sha256")
    dataset_hash = payload.get("dataset_hash")
    dataset_description = payload.get("dataset_description")
    feature_names = payload.get("feature_names")
    metrics = payload.get("metrics")
    synthetic = payload.get("synthetic")
    if not isinstance(model_version, str) or not model_version.strip():
        raise ModelArtifactError("model_version is required")
    if not isinstance(artifact_name, str) or not artifact_name.strip():
        raise ModelArtifactError("artifact is required")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ModelArtifactError("sha256 is required")
    if not isinstance(dataset_hash, str) or not dataset_hash.strip():
        raise ModelArtifactError("dataset_hash is required")
    if not isinstance(dataset_description, str):
        raise ModelArtifactError("dataset_description is required")
    if not isinstance(feature_names, list) or not all(
        isinstance(name, str) for name in feature_names
    ):
        raise ModelArtifactError("feature_names are required")
    if not isinstance(metrics, dict):
        raise ModelArtifactError("metrics are required")
    if not isinstance(synthetic, bool):
        raise ModelArtifactError("synthetic flag is required")

    artifact_path = _resolve_inside(root, artifact_name)
    if not artifact_path.is_file():
        raise ModelArtifactError("model artifact not found")
    actual_hash = _sha256(artifact_path)
    if not hmac.compare_digest(actual_hash, expected_hash):
        raise ModelArtifactError("model artifact hash mismatch")

    return ArtifactInfo(
        model_version=model_version,
        artifact_path=artifact_path,
        sha256=actual_hash,
        dataset_hash=dataset_hash,
        dataset_description=dataset_description,
        synthetic=synthetic,
        feature_names=tuple(feature_names),
        metrics=metrics,
    )


class JoblibFraudModel:
    def __init__(self, info: ArtifactInfo) -> None:
        try:
            payload: object = joblib.load(info.artifact_path)
        except Exception as exc:
            raise ModelArtifactError("cannot load model artifact") from exc
        if not isinstance(payload, dict):
            raise ModelArtifactError("invalid model artifact")
        feature_names = payload.get("feature_names")
        if not isinstance(feature_names, list) or tuple(feature_names) != FEATURE_NAMES:
            raise ModelArtifactError("feature names do not match")
        model = payload.get("model")
        anomaly_model = payload.get("anomaly_model")
        anomaly_min = payload.get("anomaly_min")
        anomaly_max = payload.get("anomaly_max")
        if model is None or anomaly_model is None:
            raise ModelArtifactError("model payload is incomplete")
        if not isinstance(anomaly_min, int | float) or not isinstance(
            anomaly_max,
            int | float,
        ):
            raise ModelArtifactError("anomaly calibration is missing")
        if anomaly_max <= anomaly_min:
            raise ModelArtifactError("anomaly calibration is invalid")

        self._info = info
        self._model = model
        self._anomaly_model = anomaly_model
        self._anomaly_min = float(anomaly_min)
        self._anomaly_max = float(anomaly_max)

    @classmethod
    def from_directory(
        cls,
        model_dir: Path,
        registry_name: str = DEFAULT_REGISTRY_NAME,
    ) -> "JoblibFraudModel":
        return cls(load_registry(model_dir, registry_name))

    @property
    def available(self) -> bool:
        return True

    def predict(self, features: tuple[float, ...]) -> ModelPrediction:
        if len(features) != len(FEATURE_NAMES):
            raise ValueError("feature vector has the wrong length")
        matrix = np.asarray([features], dtype=float)
        probability = float(self._model.predict_proba(matrix)[0, 1])
        raw_anomaly = -float(self._anomaly_model.score_samples(matrix)[0])
        normalized = (raw_anomaly - self._anomaly_min) / (self._anomaly_max - self._anomaly_min)
        return ModelPrediction(
            probability=max(0.0, min(1.0, probability)),
            anomaly_score=max(0.0, min(1.0, normalized)),
            model_version=self._info.model_version,
            synthetic=self._info.synthetic,
        )


def load_fraud_model_or_none(
    model_dir: Path,
    registry_name: str = DEFAULT_REGISTRY_NAME,
) -> "JoblibFraudModel | None":
    try:
        return JoblibFraudModel.from_directory(model_dir, registry_name)
    except Exception:
        _logger.error("fraud_model_unavailable")
        return None
