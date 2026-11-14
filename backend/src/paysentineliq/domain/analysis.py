from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from paysentineliq.domain.scoring import RiskBand


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"


class AnalysisEventType(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    RULE_TRIGGERED = "rule_triggered"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"


class DegradationFlag(StrEnum):
    LLM_UNAVAILABLE = "llm_unavailable"
    RAG_UNAVAILABLE = "rag_unavailable"
    ML_UNAVAILABLE = "ml_unavailable"


class AnalysisDocumentType(StrEnum):
    BOLETO = "boleto"
    PAYSLIP = "payslip"


@dataclass(frozen=True, slots=True)
class AnalysisEvent:
    analysis_id: UUID
    event_type: AnalysisEventType
    rule_code: str | None = None
    rule_set_version: str | None = None
    model_version: str | None = None
    degradation_flags: tuple[DegradationFlag, ...] = ()
    payload: Mapping[str, str] = field(default_factory=dict)
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.analysis_id, UUID):
            raise ValueError("analysis_id must be a UUID")
        for key, value in self.payload.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("event payload must contain string keys and values")
        if len(self.payload) > 20:
            raise ValueError("event payload is too large")


@dataclass(frozen=True, slots=True)
class AnalysisEvidence:
    rule_id: str
    severity: str
    weight: int
    message_key: str
    source: str


@dataclass(frozen=True, slots=True)
class AnalysisRecord:
    id: UUID
    owner_id: UUID
    document_id: UUID
    document_type: AnalysisDocumentType
    status: AnalysisStatus
    score: int | None
    band: RiskBand | None
    rule_set_version: str | None
    model_versions: Mapping[str, str]
    degradation_flags: tuple[DegradationFlag, ...]
    state: Mapping[str, object]
    report_s3_key: str | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    analysis_id: UUID
    document_id: UUID
    document_type: AnalysisDocumentType
    score: int
    band: RiskBand
    base_score: int
    llm_adjustment: int
    fields: Mapping[str, object]
    evidence: tuple[AnalysisEvidence, ...]
    justification: str
    inconsistencies: tuple[str, ...]
    rule_set_version: str
    model_versions: Mapping[str, str]
    degradation_flags: tuple[DegradationFlag, ...]
    report_s3_key: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")
        if not 0 <= self.base_score <= 100:
            raise ValueError("base_score must be between 0 and 100")
        if not 0 <= self.llm_adjustment <= 20:
            raise ValueError("llm_adjustment must be between 0 and 20")
        if not self.justification.strip():
            raise ValueError("justification is required")
        if len(self.inconsistencies) > 5:
            raise ValueError("at most five inconsistencies are allowed")
        if not self.report_s3_key.strip():
            raise ValueError("report_s3_key is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "analysis_id": str(self.analysis_id),
            "document_id": str(self.document_id),
            "document_type": self.document_type.value,
            "score": self.score,
            "band": self.band.value,
            "base_score": self.base_score,
            "llm_adjustment": self.llm_adjustment,
            "fields": _jsonable(self.fields),
            "evidence": [
                {
                    "rule_id": item.rule_id,
                    "severity": item.severity,
                    "weight": item.weight,
                    "message_key": item.message_key,
                    "source": item.source,
                }
                for item in self.evidence
            ],
            "justification": self.justification,
            "inconsistencies": list(self.inconsistencies),
            "rule_set_version": self.rule_set_version,
            "model_versions": dict(self.model_versions),
            "degradation_flags": [flag.value for flag in self.degradation_flags],
            "report_s3_key": self.report_s3_key,
            "created_at": self.created_at.isoformat(),
        }
