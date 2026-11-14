import httpx
import pytest

from paysentineliq.infrastructure.observability.metrics import PlatformMetrics
from paysentineliq.infrastructure.observability.queue_depth import (
    QueueDepthMonitor,
    RabbitMqQueueDepthProvider,
)

pytestmark = pytest.mark.unit


def _provider(
    payload: object,
    *,
    status_code: int = 200,
) -> RabbitMqQueueDepthProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path in {"/api/queues/%2F", "/api/queues//"}
        return httpx.Response(status_code, json=payload)

    return RabbitMqQueueDepthProvider(
        base_url="http://rabbitmq:15672",
        username="user",
        password="pass",
        transport=httpx.MockTransport(handler),
    )


async def test_provider_reads_known_queue_depths_and_ignores_unknown() -> None:
    provider = _provider(
        [
            {"name": "analysis", "messages": 7},
            {"name": "notifications", "messages": 2},
            {"name": "other", "messages": 99},
            {"name": "scheduler", "messages": "bad"},
        ],
    )

    depths = await provider.fetch()

    assert depths == {"analysis": 7, "notifications": 2}


async def test_monitor_updates_gauges_and_keeps_zero_for_missing_queues() -> None:
    metrics = PlatformMetrics(multiprocess=False)
    monitor = QueueDepthMonitor(
        _provider([{"name": "analysis", "messages": 4}]),
        metrics,
        interval_seconds=15.0,
    )

    await monitor.refresh_once()

    text = metrics.render().decode("utf-8")
    assert 'paysentineliq_queue_depth{queue="analysis"} 4.0' in text
    assert 'paysentineliq_queue_depth{queue="notifications"} 0.0' in text


async def test_monitor_failure_is_safe_and_does_not_raise() -> None:
    metrics = PlatformMetrics(multiprocess=False)
    monitor = QueueDepthMonitor(
        _provider({"error": "unavailable"}, status_code=500),
        metrics,
        interval_seconds=15.0,
    )

    await monitor.refresh_once()

    text = metrics.render().decode("utf-8")
    assert 'paysentineliq_queue_depth{queue="analysis"} 0.0' in text
