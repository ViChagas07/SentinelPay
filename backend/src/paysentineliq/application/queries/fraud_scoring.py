import logging
from dataclasses import dataclass

from paysentineliq.application.ports.fraud_model import FraudModelPort
from paysentineliq.application.queries.fraud_features import (
    build_feature_vector,
    visual_score,
)
from paysentineliq.domain.ingestion import VisualSignal
from paysentineliq.domain.scoring import (
    DeterministicSummary,
    FraudScore,
    ScoringConfig,
    fuse_risk,
)

_logger = logging.getLogger("paysentineliq")


@dataclass(frozen=True, slots=True)
class FraudScoringRequest:
    deterministic: DeterministicSummary
    visual_signals: tuple[VisualSignal, ...] = ()


class FraudScoringService:
    def __init__(
        self,
        *,
        model: FraudModelPort | None = None,
        config: ScoringConfig | None = None,
    ) -> None:
        self._model = model
        self._config = config if config is not None else ScoringConfig()

    def score(self, request: FraudScoringRequest) -> FraudScore:
        visual = visual_score(request.visual_signals)
        ml_probability: float | None = None
        anomaly_score: float | None = None
        model_version: str | None = None
        ml_synthetic: bool | None = None
        ml_unavailable = True

        if self._model is not None:
            try:
                if self._model.available:
                    prediction = self._model.predict(
                        build_feature_vector(
                            request.deterministic,
                            request.visual_signals,
                        ),
                    )
                    ml_probability = prediction.probability
                    anomaly_score = prediction.anomaly_score
                    model_version = prediction.model_version
                    ml_synthetic = prediction.synthetic
                    ml_unavailable = False
            except Exception:
                _logger.error("fraud_model_prediction_failed")
                ml_probability = None
                anomaly_score = None
                model_version = None
                ml_synthetic = None
                ml_unavailable = True

        fused = fuse_risk(
            deterministic_score=request.deterministic.subscore,
            critical_present=request.deterministic.critical_present,
            ml_probability=ml_probability,
            anomaly_score=anomaly_score,
            visual_score=visual,
            config=self._config,
        )
        return FraudScore(
            score=fused.score,
            band=fused.band,
            deterministic_score=request.deterministic.subscore,
            ml_probability=ml_probability,
            anomaly_score=anomaly_score,
            visual_score=visual,
            ml_component=fused.ml_component,
            visual_component=fused.visual_component,
            critical_floor_applied=fused.critical_floor_applied,
            ml_unavailable=ml_unavailable,
            model_version=model_version,
            ml_synthetic=ml_synthetic,
            calibration_note=self._config.calibration_note,
        )
