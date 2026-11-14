import pytest
from prometheus_client import CONTENT_TYPE_LATEST

from paysentineliq.infrastructure.observability.metrics import (
    KNOWN_QUEUES,
    PlatformMetrics,
)

pytestmark = pytest.mark.unit


def _text(metrics: PlatformMetrics) -> str:
    return metrics.render().decode("utf-8")


def test_metrics_expose_named_series_and_safe_labels() -> None:
    metrics = PlatformMetrics(multiprocess=False)
    metrics.record_http_request("GET", "/api/v1/analyses/{analysis_id}", 200, 0.12)
    metrics.record_rate_limit("ip")
    metrics.record_analysis("boleto", "low")
    metrics.record_pipeline_stage("ingest", "boleto", 0.5)
    metrics.record_llm("fake-model", "success", 0.2)
    metrics.record_guardrail_block("injection_patterns")
    metrics.set_queue_depth("analysis", 3)
    metrics.record_notification("email", "sent")
    metrics.record_cache("hit")

    text = _text(metrics)

    for name in (
        "paysentineliq_http_requests_total",
        "paysentineliq_http_request_duration_seconds",
        "paysentineliq_http_429_total",
        "paysentineliq_analyses_total",
        "paysentineliq_pipeline_stage_duration_seconds",
        "paysentineliq_llm_requests_total",
        "paysentineliq_llm_request_duration_seconds",
        "paysentineliq_guardrail_blocks_total",
        "paysentineliq_queue_depth",
        "paysentineliq_notifications_total",
        "paysentineliq_cache_events_total",
    ):
        assert name in text
    assert 'document_type="boleto"' in text
    assert 'band="low"' in text
    assert 'stage="ingest"' in text
    assert 'queue="analysis"' in text
    assert 'channel="email"' in text
    assert 'result="hit"' in text
    assert metrics.content_type == CONTENT_TYPE_LATEST


def test_queue_gauges_are_initialized_for_known_queues() -> None:
    metrics = PlatformMetrics(multiprocess=False)

    text = _text(metrics)

    for queue in KNOWN_QUEUES:
        assert f'queue="{queue}"' in text


def test_raw_paths_are_normalized_and_pii_is_never_in_labels() -> None:
    metrics = PlatformMetrics(multiprocess=False)
    metrics.record_http_request(
        "POST",
        "/api/v1/analyses/123e4567-e89b-12d3-a456-426614174000?email=user@example.com",
        200,
        0.1,
    )
    metrics.record_analysis("boleto", "low")
    metrics.record_notification("email", "sent")

    text = _text(metrics)

    assert "/api/v1/analyses/{id}" in text
    assert "123e4567-e89b-12d3-a456-426614174000" not in text
    assert "user@example.com" not in text
    assert "user_id=" not in text
    assert "document_id=" not in text
    assert "analysis_id=" not in text
    assert "cpf=" not in text


def test_unknown_label_values_are_collapsed() -> None:
    metrics = PlatformMetrics(multiprocess=False)
    metrics.record_http_request("GET", "/raw/path/with-free-text", 200, 0.1)
    metrics.record_notification("carrier-pigeon", "sent")
    metrics.record_cache("weird")

    text = _text(metrics)

    assert 'channel="other"' in text
    assert 'result="other"' in text
