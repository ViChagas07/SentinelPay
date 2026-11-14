import pytest

from paysentineliq.domain.scoring import (
    RiskBand,
    ScoringConfig,
    SeverityLevel,
    fuse_risk,
)

pytestmark = pytest.mark.unit


def test_default_config_weights_and_cuts() -> None:
    config = ScoringConfig()

    assert config.deterministic_weight + config.ml_weight + config.visual_weight == pytest.approx(
        1.0
    )
    assert config.low_max < config.attention_max
    assert config.critical_floor == 80
    assert config.calibration_note == "a calibrar com dados reais"


def test_fuse_with_ml_uses_all_components() -> None:
    result = fuse_risk(
        deterministic_score=20,
        critical_present=False,
        ml_probability=0.8,
        anomaly_score=0.5,
        visual_score=0.2,
        config=ScoringConfig(),
    )

    assert result.ml_component == pytest.approx(74.0)
    assert result.score == 36
    assert result.band is RiskBand.LOW
    assert result.ml_unavailable is False
    assert result.critical_floor_applied is False


def test_fuse_without_ml_renormalizes_remaining_weights() -> None:
    result = fuse_risk(
        deterministic_score=40,
        critical_present=False,
        ml_probability=None,
        anomaly_score=None,
        visual_score=1.0,
        config=ScoringConfig(),
    )

    assert result.ml_component is None
    assert result.score == 49
    assert result.band is RiskBand.ATTENTION
    assert result.ml_unavailable is True


def test_critical_rule_imposes_floor() -> None:
    result = fuse_risk(
        deterministic_score=10,
        critical_present=True,
        ml_probability=0.1,
        anomaly_score=0.0,
        visual_score=0.0,
        config=ScoringConfig(),
    )

    assert result.score == 80
    assert result.band is RiskBand.HIGH
    assert result.critical_floor_applied is True


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (0, RiskBand.LOW),
        (39, RiskBand.LOW),
        (40, RiskBand.ATTENTION),
        (69, RiskBand.ATTENTION),
        (70, RiskBand.HIGH),
        (100, RiskBand.HIGH),
    ],
)
def test_band_cuts(score: int, band: RiskBand) -> None:
    result = fuse_risk(
        deterministic_score=score,
        critical_present=False,
        ml_probability=None,
        anomaly_score=None,
        visual_score=0.0,
        config=ScoringConfig(deterministic_weight=1.0, ml_weight=0.0, visual_weight=0.0),
    )

    assert result.score == score
    assert result.band is band


def test_more_critical_evidence_does_not_reduce_score() -> None:
    low = fuse_risk(
        deterministic_score=20,
        critical_present=False,
        ml_probability=0.5,
        anomaly_score=0.3,
        visual_score=0.2,
        config=ScoringConfig(),
    )
    high = fuse_risk(
        deterministic_score=80,
        critical_present=True,
        ml_probability=0.5,
        anomaly_score=0.3,
        visual_score=0.2,
        config=ScoringConfig(),
    )

    assert high.score >= low.score
    assert high.score >= 80


def test_positive_critical_severity_is_required_for_floor() -> None:
    result = fuse_risk(
        deterministic_score=0,
        critical_present=False,
        ml_probability=0.0,
        anomaly_score=0.0,
        visual_score=0.0,
        config=ScoringConfig(),
    )

    assert result.score == 0
    assert result.critical_floor_applied is False


def test_config_rejects_invalid_weights_and_cuts() -> None:
    with pytest.raises(ValueError):
        ScoringConfig(deterministic_weight=0.5, ml_weight=0.4, visual_weight=0.2)
    with pytest.raises(ValueError):
        ScoringConfig(low_max=70, attention_max=69)
    with pytest.raises(ValueError):
        ScoringConfig(anomaly_weight=1.5)
    with pytest.raises(ValueError):
        ScoringConfig(deterministic_weight=0.0, ml_weight=1.0, visual_weight=0.0)


def test_severity_level_values_match_inputs() -> None:
    assert SeverityLevel.CRITICAL.value == "critical"
    assert SeverityLevel.HIGH.value == "high"
