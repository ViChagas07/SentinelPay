import hashlib
import json
import shutil
from pathlib import Path

import joblib
import pytest

from paysentineliq.infrastructure.ml.artifact import (
    JoblibFraudModel,
    ModelArtifactError,
    load_fraud_model_or_none,
    load_registry,
)
from paysentineliq.infrastructure.ml.synthetic import (
    SyntheticDataset,
    SyntheticDatasetConfig,
    generate_synthetic_dataset,
)
from paysentineliq.infrastructure.ml.training import (
    TrainingConfig,
    TrainingResult,
    train_fraud_model,
)

pytestmark = pytest.mark.unit

_REGISTRY = "fraud-risk-v1.json"


@pytest.fixture(scope="module")
def trained(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[SyntheticDataset, TrainingResult, Path]:
    output = tmp_path_factory.mktemp("artifacts")
    dataset = generate_synthetic_dataset(
        SyntheticDatasetConfig(seed=42, base_documents=24, variants_per_base=2),
    )
    result = train_fraud_model(
        dataset,
        output,
        TrainingConfig(seed=42, calibration_cv=2),
    )
    return dataset, result, output


def test_training_writes_artifact_registry_and_synthetic_metrics(
    trained: tuple[SyntheticDataset, TrainingResult, Path],
) -> None:
    dataset, result, output = trained

    assert result.artifact_path.exists()
    assert result.registry_path.exists()
    assert result.artifact_path.parent == output
    assert result.dataset_hash == dataset.hash
    assert result.metrics["synthetic"] is True
    assert result.metrics["dataset_origin"] == "synthetic"
    assert {"precision", "recall", "f1", "roc_auc", "pr_auc", "brier"} <= set(
        result.metrics,
    )
    payload = json.loads(result.registry_path.read_text(encoding="utf-8"))
    assert payload["sha256"] == result.artifact_sha256
    assert payload["dataset_hash"] == dataset.hash
    assert payload["synthetic"] is True
    assert payload["feature_names"] == list(result.feature_names)
    assert payload["metrics"] == result.metrics


def test_artifact_sha256_matches_file(
    trained: tuple[SyntheticDataset, TrainingResult, Path],
) -> None:
    _, result, _ = trained
    digest = hashlib.sha256(result.artifact_path.read_bytes()).hexdigest()

    assert digest == result.artifact_sha256


def test_loader_verifies_and_loads_artifact(
    trained: tuple[SyntheticDataset, TrainingResult, Path],
) -> None:
    dataset, result, output = trained

    info = load_registry(output, _REGISTRY)
    model = JoblibFraudModel.from_directory(output, _REGISTRY)
    prediction = model.predict(dataset.rows[0].features)

    assert info.sha256 == result.artifact_sha256
    assert model.available is True
    assert 0.0 <= prediction.probability <= 1.0
    assert 0.0 <= prediction.anomaly_score <= 1.0
    assert prediction.synthetic is True
    assert prediction.model_version == result.model_version


def test_tampered_artifact_is_rejected(
    trained: tuple[SyntheticDataset, TrainingResult, Path],
    tmp_path: Path,
) -> None:
    _, result, _ = trained
    shutil.copy2(result.artifact_path, tmp_path / result.artifact_path.name)
    shutil.copy2(result.registry_path, tmp_path / _REGISTRY)
    artifact = tmp_path / result.artifact_path.name
    artifact.write_bytes(artifact.read_bytes() + b"tamper")

    with pytest.raises(ModelArtifactError):
        load_registry(tmp_path, _REGISTRY)
    assert load_fraud_model_or_none(tmp_path, _REGISTRY) is None


def test_registry_path_traversal_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ModelArtifactError):
        load_registry(tmp_path, "../fraud-risk-v1.json")


def test_artifact_path_traversal_is_rejected(tmp_path: Path) -> None:
    registry = {
        "schema_version": 1,
        "model_version": "fraud-risk-v1",
        "artifact": "../outside.joblib",
        "sha256": "0" * 64,
        "dataset_hash": "0" * 64,
        "dataset_description": "synthetic",
        "synthetic": True,
        "feature_names": [],
        "metrics": {},
    }
    (tmp_path / _REGISTRY).write_text(json.dumps(registry), encoding="utf-8")

    with pytest.raises(ModelArtifactError):
        load_registry(tmp_path, _REGISTRY)


def test_feature_names_mismatch_is_rejected(
    trained: tuple[SyntheticDataset, TrainingResult, Path],
    tmp_path: Path,
) -> None:
    _, result, _ = trained
    artifact = tmp_path / result.artifact_path.name
    shutil.copy2(result.artifact_path, artifact)
    payload = joblib.load(artifact)
    payload["feature_names"] = ["wrong"]
    joblib.dump(payload, artifact)
    registry = json.loads(result.registry_path.read_text(encoding="utf-8"))
    registry["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (tmp_path / _REGISTRY).write_text(json.dumps(registry), encoding="utf-8")

    with pytest.raises(ModelArtifactError):
        JoblibFraudModel.from_directory(tmp_path, _REGISTRY)


def test_missing_registry_returns_none(tmp_path: Path) -> None:
    assert load_fraud_model_or_none(tmp_path, "missing.json") is None


def test_training_is_deterministic(tmp_path: Path) -> None:
    dataset = generate_synthetic_dataset(
        SyntheticDatasetConfig(seed=7, base_documents=20, variants_per_base=2),
    )
    first = train_fraud_model(
        dataset,
        tmp_path / "first",
        TrainingConfig(seed=7, calibration_cv=2),
    )
    second = train_fraud_model(
        dataset,
        tmp_path / "second",
        TrainingConfig(seed=7, calibration_cv=2),
    )

    assert first.metrics == second.metrics
    first_model = JoblibFraudModel.from_directory(tmp_path / "first", _REGISTRY)
    second_model = JoblibFraudModel.from_directory(tmp_path / "second", _REGISTRY)
    sample = dataset.rows[0].features
    first_prediction = first_model.predict(sample)
    second_prediction = second_model.predict(sample)
    assert first_prediction.probability == pytest.approx(second_prediction.probability)
    assert first_prediction.anomaly_score == pytest.approx(
        second_prediction.anomaly_score,
    )


def test_loader_returns_available_model(
    trained: tuple[SyntheticDataset, TrainingResult, Path],
) -> None:
    _, _, output = trained
    model = load_fraud_model_or_none(output, _REGISTRY)

    assert model is not None
    assert model.available is True
