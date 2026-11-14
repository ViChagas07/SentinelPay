from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ModelPrediction:
    probability: float
    anomaly_score: float
    model_version: str
    synthetic: bool

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError("probability must be between 0 and 1")
        if not 0.0 <= self.anomaly_score <= 1.0:
            raise ValueError("anomaly_score must be between 0 and 1")
        if not self.model_version.strip():
            raise ValueError("model_version is required")


class FraudModelPort(Protocol):
    @property
    def available(self) -> bool: ...

    def predict(self, features: tuple[float, ...]) -> ModelPrediction: ...
