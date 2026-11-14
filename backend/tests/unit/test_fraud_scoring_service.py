import pytest

from paysentineliq.application.ports.fraud_model import ModelPrediction
from paysentineliq.application.queries.fraud_scoring import (
    FraudScoringRequest,
    FraudScoringService,
)
from paysentineliq.domain.ingestion import VisualSignal
from paysentineliq.domain.scoring import (
    DeterministicSummary,
    EvidenceSummary,
    RiskBand,
    SeverityLevel,
)

pytestmark = pytest.mark.unit


def _summary(
    *,
    subscore: int = 0,
    critical: bool = False,
) -> DeterministicSummary:
    evidence = (
        (
            EvidenceSummary(
                rule_id="dv_invalid",
                severity=SeverityLevel.CRITICAL,
                weight=70,
            ),
        )
        if critical
        else ()
    )
    return DeterministicSummary(
        document_type="boleto",
        subscore=subscore,
        evidence=evidence,
        field_confidences=(0.95, 0.9),
        not_validated_count=0,
        amount_cents=100000,
        due_factor=9000,
    )


class FakeModel:
    def __init__(
        self,
        prediction: ModelPrediction | None = None,
        *,
        available: bool = True,
        error: Exception | None = None,
    ) -> None:
        self._prediction = prediction
        self._available = available
        self._error = error
        self.calls = 0

    @property
    def available(self) -> bool:
        return self._available

    def predict(self, features: tuple[float, ...]) -> ModelPrediction:
        self.calls += 1
        if self._error is not None:
            raise self._error
        if self._prediction is None:
            raise RuntimeError("no prediction")
        return self._prediction


def _prediction(
    *,
    probability: float = 0.8,
    anomaly_score: float = 0.5,
    synthetic: bool = True,
) -> ModelPrediction:
    return ModelPrediction(
        probability=probability,
        anomaly_score=anomaly_score,
        model_version="fake-v1",
        synthetic=synthetic,
    )


def test_without_model_falls_back_to_deterministic_and_visual() -> None:
    service = FraudScoringService()
    signals = (VisualSignal(name="image_blur", value=0.5, explanation="synthetic"),)

    result = service.score(
        FraudScoringRequest(
            deterministic=_summary(subscore=40),
            visual_signals=signals,
        ),
    )

    assert result.score == 41
    assert result.band is RiskBand.ATTENTION
    assert result.ml_unavailable is True
    assert result.ml_probability is None
    assert result.model_version is None
    assert result.ml_synthetic is None
    assert result.calibration_note == "a calibrar com dados reais"


def test_with_fake_model_uses_ml_and_marks_synthetic() -> None:
    model = FakeModel(_prediction())
    service = FraudScoringService(model=model)
    signals = (VisualSignal(name="image_noise", value=0.2, explanation="synthetic"),)

    result = service.score(
        FraudScoringRequest(
            deterministic=_summary(subscore=20),
            visual_signals=signals,
        ),
    )

    assert model.calls == 1
    assert result.score == 36
    assert result.ml_unavailable is False
    assert result.ml_probability == 0.8
    assert result.anomaly_score == 0.5
    assert result.ml_component == pytest.approx(74.0)
    assert result.model_version == "fake-v1"
    assert result.ml_synthetic is True


def test_without_model_uses_visual_only() -> None:
    service = FraudScoringService()

    result = service.score(
        FraudScoringRequest(
            deterministic=_summary(subscore=0),
            visual_signals=(
                VisualSignal(name="copy_move_orb", value=1.0, explanation="synthetic"),
            ),
        ),
    )

    assert result.score == 14
    assert result.band is RiskBand.LOW


def test_critical_rule_imposes_floor_in_service() -> None:
    model = FakeModel(
        _prediction(probability=0.1, anomaly_score=0.0),
    )
    service = FraudScoringService(model=model)

    result = service.score(
        FraudScoringRequest(deterministic=_summary(subscore=10, critical=True)),
    )

    assert result.score == 80
    assert result.band is RiskBand.HIGH
    assert result.critical_floor_applied is True


def test_more_critical_evidence_does_not_reduce_score() -> None:
    service = FraudScoringService(model=FakeModel(_prediction()))

    low = service.score(FraudScoringRequest(deterministic=_summary(subscore=20)))
    high = service.score(
        FraudScoringRequest(deterministic=_summary(subscore=80, critical=True)),
    )

    assert high.score >= low.score
    assert high.score >= 80


def test_model_failure_falls_back_without_raising() -> None:
    service = FraudScoringService(model=FakeModel(error=RuntimeError("boom")))

    result = service.score(
        FraudScoringRequest(
            deterministic=_summary(subscore=20),
            visual_signals=(VisualSignal(name="image_blur", value=0.3, explanation="synthetic"),),
        ),
    )

    assert result.ml_unavailable is True
    assert result.ml_probability is None
    assert result.score == 21


def test_unavailable_model_is_not_called() -> None:
    model = FakeModel(_prediction(), available=False)
    service = FraudScoringService(model=model)

    result = service.score(FraudScoringRequest(deterministic=_summary(subscore=0)))

    assert model.calls == 0
    assert result.ml_unavailable is True
    assert result.score == 0


def test_prediction_validation() -> None:
    with pytest.raises(ValueError):
        ModelPrediction(
            probability=1.5,
            anomaly_score=0.5,
            model_version="fake",
            synthetic=True,
        )
