import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal


class SeverityLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RiskBand(StrEnum):
    LOW = "low"
    ATTENTION = "attention"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class EvidenceSummary:
    rule_id: str
    severity: SeverityLevel
    weight: int

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("rule_id is required")
        if self.weight < 0:
            raise ValueError("weight must be non-negative")


@dataclass(frozen=True, slots=True)
class DeterministicSummary:
    document_type: Literal["boleto", "payslip"]
    subscore: int
    evidence: tuple[EvidenceSummary, ...]
    field_confidences: tuple[float, ...]
    not_validated_count: int
    amount_cents: int | None = None
    due_factor: int | None = None
    barcode_read: bool | None = None
    has_unknown_items: bool = False
    item_count: int = 0
    total_earnings: Decimal | None = None
    total_deductions: Decimal | None = None
    net: Decimal | None = None

    def __post_init__(self) -> None:
        if self.document_type not in ("boleto", "payslip"):
            raise ValueError("document_type must be boleto or payslip")
        if not 0 <= self.subscore <= 100:
            raise ValueError("subscore must be between 0 and 100")
        if any(not 0.0 <= value <= 1.0 for value in self.field_confidences):
            raise ValueError("field confidences must be between 0 and 1")
        if self.not_validated_count < 0 or self.item_count < 0:
            raise ValueError("counts must be non-negative")
        if self.amount_cents is not None and self.amount_cents < 0:
            raise ValueError("amount_cents must be non-negative")
        if self.due_factor is not None and not 0 <= self.due_factor <= 9999:
            raise ValueError("due_factor must be between 0 and 9999")
        for value in (self.total_earnings, self.total_deductions, self.net):
            if value is not None and not value.is_finite():
                raise ValueError("monetary values must be finite")

    @property
    def critical_present(self) -> bool:
        return any(evidence.severity is SeverityLevel.CRITICAL for evidence in self.evidence)


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    deterministic_weight: float = 0.60
    ml_weight: float = 0.30
    visual_weight: float = 0.10
    anomaly_weight: float = 0.20
    low_max: int = 39
    attention_max: int = 69
    critical_floor: int = 80
    calibration_note: str = "a calibrar com dados reais"

    def __post_init__(self) -> None:
        weights = (self.deterministic_weight, self.ml_weight, self.visual_weight)
        if any(not 0.0 <= weight <= 1.0 for weight in weights):
            raise ValueError("weights must be between 0 and 1")
        if not math.isclose(sum(weights), 1.0, abs_tol=1e-9):
            raise ValueError("weights must sum to 1")
        if self.deterministic_weight + self.visual_weight <= 0:
            raise ValueError("deterministic or visual weight is required for fallback")
        if not 0.0 <= self.anomaly_weight <= 1.0:
            raise ValueError("anomaly_weight must be between 0 and 1")
        if not 0 <= self.low_max < self.attention_max <= 100:
            raise ValueError("cuts must satisfy 0 <= low_max < attention_max <= 100")
        if not 0 <= self.critical_floor <= 100:
            raise ValueError("critical_floor must be between 0 and 100")
        if not self.calibration_note.strip():
            raise ValueError("calibration_note is required")


@dataclass(frozen=True, slots=True)
class FusedScore:
    score: int
    band: RiskBand
    deterministic_component: float
    ml_component: float | None
    visual_component: float
    ml_unavailable: bool
    critical_floor_applied: bool


def _round_score(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def fuse_risk(
    deterministic_score: int,
    critical_present: bool,
    ml_probability: float | None,
    anomaly_score: float | None,
    visual_score: float,
    config: ScoringConfig,
) -> FusedScore:
    if not 0 <= deterministic_score <= 100:
        raise ValueError("deterministic_score must be between 0 and 100")
    if not 0.0 <= visual_score <= 1.0:
        raise ValueError("visual_score must be between 0 and 1")
    if ml_probability is not None and not 0.0 <= ml_probability <= 1.0:
        raise ValueError("ml_probability must be between 0 and 1")
    if anomaly_score is not None and not 0.0 <= anomaly_score <= 1.0:
        raise ValueError("anomaly_score must be between 0 and 1")

    ml_unavailable = ml_probability is None or anomaly_score is None
    if ml_probability is None or anomaly_score is None:
        remaining = config.deterministic_weight + config.visual_weight
        det_weight = config.deterministic_weight / remaining
        visual_weight = config.visual_weight / remaining
        ml_component: float | None = None
        raw = det_weight * deterministic_score + visual_weight * visual_score * 100
    else:
        ml_component = (
            ml_probability * (1.0 - config.anomaly_weight) + anomaly_score * config.anomaly_weight
        ) * 100
        raw = (
            config.deterministic_weight * deterministic_score
            + config.ml_weight * ml_component
            + config.visual_weight * visual_score * 100
        )

    critical_floor_applied = critical_present and raw < config.critical_floor
    if critical_floor_applied:
        raw = float(config.critical_floor)
    score = min(100, max(0, _round_score(raw)))
    if score <= config.low_max:
        band = RiskBand.LOW
    elif score <= config.attention_max:
        band = RiskBand.ATTENTION
    else:
        band = RiskBand.HIGH

    return FusedScore(
        score=score,
        band=band,
        deterministic_component=float(deterministic_score),
        ml_component=ml_component,
        visual_component=visual_score * 100,
        ml_unavailable=ml_unavailable,
        critical_floor_applied=critical_floor_applied,
    )
