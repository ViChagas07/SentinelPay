from pathlib import Path

import pytest

from paysentineliq.infrastructure.guardrails.synthetic import (
    InjectionDatasetConfig,
    generate_injection_dataset,
)
from paysentineliq.infrastructure.guardrails.training import (
    SklearnInjectionClassifier,
    load_injection_classifier,
    train_injection_classifier,
)


@pytest.fixture(scope="session")
def synthetic_classifier(tmp_path_factory: pytest.TempPathFactory) -> SklearnInjectionClassifier:
    directory: Path = tmp_path_factory.mktemp("guardrail-model")
    dataset = generate_injection_dataset(
        InjectionDatasetConfig(seed=42, injection_variants=80, benign_variants=80),
    )
    train_injection_classifier(dataset, directory)
    return load_injection_classifier(directory)
