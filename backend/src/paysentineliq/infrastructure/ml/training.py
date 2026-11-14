import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from paysentineliq.application.queries.fraud_features import FEATURE_NAMES
from paysentineliq.infrastructure.ml.synthetic import (
    DatasetRow,
    SyntheticDataset,
    split_rows_by_base,
)


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    model_version: str = "fraud-risk-v1"
    seed: int = 42
    validation_fraction: float = 0.2
    test_fraction: float = 0.2
    calibration_cv: int = 3
    anomaly_estimators: int = 100

    def __post_init__(self) -> None:
        if not self.model_version.strip():
            raise ValueError("model_version is required")
        if "/" in self.model_version or "\\" in self.model_version:
            raise ValueError("model_version must not contain path separators")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if not 0.0 < self.validation_fraction < 1.0:
            raise ValueError("validation_fraction must be between 0 and 1")
        if not 0.0 < self.test_fraction < 1.0:
            raise ValueError("test_fraction must be between 0 and 1")
        if self.validation_fraction + self.test_fraction >= 1.0:
            raise ValueError("validation and test fractions must sum to less than 1")
        if self.calibration_cv < 2:
            raise ValueError("calibration_cv must be at least 2")
        if self.anomaly_estimators <= 0:
            raise ValueError("anomaly_estimators must be positive")


@dataclass(frozen=True, slots=True)
class TrainingResult:
    artifact_path: Path
    registry_path: Path
    artifact_sha256: str
    dataset_hash: str
    metrics: dict[str, Any]
    feature_names: tuple[str, ...]
    model_version: str


def _arrays(rows: tuple[DatasetRow, ...]) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    features = np.asarray([row.features for row in rows], dtype=float)
    labels = np.asarray([row.label for row in rows], dtype=int)
    return features, labels


def _calibration_points(
    labels: np.ndarray[Any, Any],
    probabilities: np.ndarray[Any, Any],
) -> list[dict[str, float]]:
    try:
        fraction_positive, mean_predicted = calibration_curve(
            labels,
            probabilities,
            n_bins=5,
            strategy="uniform",
        )
    except ValueError:
        return []
    return [
        {
            "mean_predicted_probability": float(predicted),
            "fraction_positive": float(positive),
        }
        for positive, predicted in zip(fraction_positive, mean_predicted, strict=True)
    ]


def _evaluate(
    labels: np.ndarray[Any, Any],
    predictions: np.ndarray[Any, Any],
    probabilities: np.ndarray[Any, Any],
) -> dict[str, Any]:
    two_classes = len(np.unique(labels)) >= 2
    roc_auc = float(roc_auc_score(labels, probabilities)) if two_classes else None
    pr_auc = float(average_precision_score(labels, probabilities)) if two_classes else None
    return {
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "brier": float(brier_score_loss(labels, probabilities)),
        "calibration_curve": _calibration_points(labels, probabilities),
    }


def train_fraud_model(
    dataset: SyntheticDataset,
    output_dir: Path,
    config: TrainingConfig | None = None,
) -> TrainingResult:
    actual = config if config is not None else TrainingConfig()
    split = split_rows_by_base(
        dataset.rows,
        seed=actual.seed,
        validation_fraction=actual.validation_fraction,
        test_fraction=actual.test_fraction,
    )
    train_x, train_y = _arrays(split.train)
    validation_x, validation_y = _arrays(split.validation)
    test_x, test_y = _arrays(split.test)

    class_counts = np.bincount(train_y)
    if len(class_counts) < 2 or int(class_counts.min()) < 2:
        raise ValueError("training data needs at least two rows per class")
    cv = min(actual.calibration_cv, int(class_counts.min()))
    classifier: Any = CalibratedClassifierCV(
        Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=1000,
                        class_weight="balanced",
                        random_state=actual.seed,
                    ),
                ),
            ],
        ),
        method="sigmoid",
        cv=cv,
    )
    classifier.fit(train_x, train_y)

    anomaly_model = IsolationForest(
        n_estimators=actual.anomaly_estimators,
        contamination="auto",
        random_state=actual.seed,
        n_jobs=1,
    )
    normal_x = train_x[train_y == 0]
    if len(normal_x) == 0:
        raise ValueError("training data needs valid rows for anomaly detection")
    anomaly_model.fit(normal_x)
    normal_scores = -anomaly_model.score_samples(normal_x)
    anomaly_min = float(np.min(normal_scores))
    anomaly_max = float(np.max(normal_scores))
    if anomaly_max <= anomaly_min:
        anomaly_max = anomaly_min + 1e-9

    test_predictions = classifier.predict(test_x)
    test_probabilities = classifier.predict_proba(test_x)[:, 1]
    validation_predictions = classifier.predict(validation_x)
    validation_probabilities = classifier.predict_proba(validation_x)[:, 1]
    metrics: dict[str, Any] = {
        "synthetic": True,
        "dataset_origin": "synthetic",
        "model_version": actual.model_version,
        "seed": actual.seed,
        "dataset_hash": dataset.hash,
        "dataset_description": dataset.description,
        "n_train": len(split.train),
        "n_validation": len(split.validation),
        "n_test": len(split.test),
        "n_train_bases": len(split.train_base_ids),
        "n_validation_bases": len(split.validation_base_ids),
        "n_test_bases": len(split.test_base_ids),
        **_evaluate(test_y, test_predictions, test_probabilities),
        "validation": _evaluate(
            validation_y,
            validation_predictions,
            validation_probabilities,
        ),
    }

    output = output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifact_path = output / f"{actual.model_version}.joblib"
    payload = {
        "schema_version": 1,
        "model_version": actual.model_version,
        "feature_names": list(FEATURE_NAMES),
        "model": classifier,
        "anomaly_model": anomaly_model,
        "anomaly_min": anomaly_min,
        "anomaly_max": anomaly_max,
        "dataset_hash": dataset.hash,
        "dataset_description": dataset.description,
        "synthetic": True,
    }
    joblib.dump(payload, artifact_path)
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()

    registry_path = output / f"{actual.model_version}.json"
    registry = {
        "schema_version": 1,
        "model_version": actual.model_version,
        "artifact": artifact_path.name,
        "sha256": digest,
        "dataset_hash": dataset.hash,
        "dataset_description": dataset.description,
        "synthetic": True,
        "feature_names": list(FEATURE_NAMES),
        "metrics": metrics,
        "calibration_note": "pesos e cortes a calibrar com dados reais",
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
        feature_names=FEATURE_NAMES,
        model_version=actual.model_version,
    )
