import pytest

from paysentineliq.domain.analysis_progress import (
    STAGE_ORDER,
    STAGE_WEIGHTS,
    AnalysisStage,
    progress_within_stage,
    stage_end_percent,
    stage_from_value,
    stage_start_percent,
)

pytestmark = pytest.mark.unit


def test_stage_weights_sum_to_one_hundred() -> None:
    assert sum(STAGE_WEIGHTS.values()) == 100
    assert list(STAGE_ORDER) == list(STAGE_WEIGHTS)


def test_stage_boundaries_are_cumulative_and_monotonic() -> None:
    previous = 0
    for stage in STAGE_ORDER:
        assert stage_start_percent(stage) == previous
        previous = stage_end_percent(stage)
    assert previous == 100


def test_progress_within_stage_is_bounded() -> None:
    start = stage_start_percent(AnalysisStage.OCR)
    end = stage_end_percent(AnalysisStage.OCR)

    assert progress_within_stage(AnalysisStage.OCR, 0.0) == start
    assert progress_within_stage(AnalysisStage.OCR, 1.0) == end
    assert start < progress_within_stage(AnalysisStage.OCR, 0.5) < end
    assert progress_within_stage(AnalysisStage.OCR, -1.0) == start
    assert progress_within_stage(AnalysisStage.OCR, 2.0) == end


def test_stage_lookup_ignores_unknown_values() -> None:
    assert stage_from_value("rag") is AnalysisStage.RAG
    assert stage_from_value("unknown") is None
    assert stage_from_value(None) is None
