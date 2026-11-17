from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class AnalysisStage(StrEnum):
    VALIDATION = "validation"
    OCR = "ocr"
    EXTRACTION = "extraction"
    CLASSIFICATION = "classification"
    RAG = "rag"
    LLM = "llm"
    PERSISTENCE = "persistence"


STAGE_ORDER: tuple[AnalysisStage, ...] = (
    AnalysisStage.VALIDATION,
    AnalysisStage.OCR,
    AnalysisStage.EXTRACTION,
    AnalysisStage.CLASSIFICATION,
    AnalysisStage.RAG,
    AnalysisStage.LLM,
    AnalysisStage.PERSISTENCE,
)

STAGE_WEIGHTS: Mapping[AnalysisStage, int] = MappingProxyType(
    {
        AnalysisStage.VALIDATION: 5,
        AnalysisStage.OCR: 25,
        AnalysisStage.EXTRACTION: 10,
        AnalysisStage.CLASSIFICATION: 10,
        AnalysisStage.RAG: 20,
        AnalysisStage.LLM: 25,
        AnalysisStage.PERSISTENCE: 5,
    },
)

_STAGE_START: Mapping[AnalysisStage, int] = MappingProxyType(
    {
        stage: sum(STAGE_WEIGHTS[item] for item in STAGE_ORDER[:index])
        for index, stage in enumerate(STAGE_ORDER)
    },
)

if sum(STAGE_WEIGHTS.values()) != 100:
    raise ValueError("analysis stage weights must sum to 100")


def stage_start_percent(stage: AnalysisStage) -> int:
    return _STAGE_START[stage]


def stage_end_percent(stage: AnalysisStage) -> int:
    return _STAGE_START[stage] + STAGE_WEIGHTS[stage]


def progress_within_stage(stage: AnalysisStage, fraction: float) -> int:
    bounded = min(1.0, max(0.0, fraction))
    start = stage_start_percent(stage)
    return min(stage_end_percent(stage), start + round(STAGE_WEIGHTS[stage] * bounded))


def stage_from_value(value: str | None) -> AnalysisStage | None:
    if value is None:
        return None
    try:
        return AnalysisStage(value)
    except ValueError:
        return None
