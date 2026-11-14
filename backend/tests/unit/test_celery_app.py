from typing import Any

import pytest
from pydantic import ValidationError

from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.messaging.celery_app import (
    ANALYSIS_QUEUE,
    DLX_NAME,
    NOTIFICATIONS_QUEUE,
    SCHEDULER_QUEUE,
    build_celery_app,
)

pytestmark = pytest.mark.unit


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "local",
        "celery_task_always_eager": True,
        "rabbitmq_url": "memory://",
        "celery_result_backend": "cache+memory://",
    }
    values.update(overrides)
    return Settings(**values)


def test_celery_app_configures_reliability_and_queues() -> None:
    app = build_celery_app(_settings())
    conf = app.conf

    assert conf.task_acks_late is True
    assert conf.task_acks_on_failure_or_timeout is False
    assert conf.task_reject_on_worker_lost is True
    assert conf.worker_prefetch_multiplier == 1
    assert conf.task_soft_time_limit == 900
    assert conf.task_time_limit == 960
    assert conf.task_default_queue == ANALYSIS_QUEUE
    assert conf.task_always_eager is True

    queues = {queue.name: queue for queue in conf.task_queues}
    assert {ANALYSIS_QUEUE, NOTIFICATIONS_QUEUE, SCHEDULER_QUEUE} <= set(queues)
    assert f"{ANALYSIS_QUEUE}.dlq" in queues
    assert queues[ANALYSIS_QUEUE].queue_arguments["x-dead-letter-exchange"] == DLX_NAME
    assert (
        queues[ANALYSIS_QUEUE].queue_arguments["x-dead-letter-routing-key"]
        == f"{ANALYSIS_QUEUE}.dlq"
    )


def test_celery_app_routes_tasks_and_schedules_sweeper() -> None:
    app = build_celery_app(_settings())
    conf = app.conf

    assert conf.task_routes["paysentineliq.analysis.run"]["queue"] == ANALYSIS_QUEUE
    assert conf.task_routes["paysentineliq.notifications.dispatch"]["queue"] == NOTIFICATIONS_QUEUE
    assert (
        conf.task_routes["paysentineliq.scheduler.sweep_stale_analyses"]["queue"] == SCHEDULER_QUEUE
    )
    schedule = conf.beat_schedule["sweep-stale-analyses"]
    assert schedule["task"] == "paysentineliq.scheduler.sweep_stale_analyses"
    assert schedule["schedule"] == 300
    assert schedule["options"]["queue"] == SCHEDULER_QUEUE
    annotations = conf.task_annotations["paysentineliq.analysis.run"]
    assert annotations["max_retries"] == 3
    assert annotations["retry_backoff"] is True
    assert annotations["retry_jitter"] is True


def test_ping_task_runs_eager_without_broker() -> None:
    app = build_celery_app(_settings())

    result = app.tasks["paysentineliq.health.ping"].delay().get(timeout=5)

    assert result == "pong"


def test_celery_settings_are_validated() -> None:
    settings = _settings()

    assert settings.analysis_max_concurrent_per_user == 2
    assert settings.analysis_task_max_retries == 3
    assert settings.analysis_lease_seconds == 900
    assert settings.analysis_stale_sweep_seconds == 300
    assert settings.fraud_model_dir

    with pytest.raises(ValidationError):
        _settings(celery_task_soft_time_limit_seconds=1000, celery_task_time_limit_seconds=900)

    with pytest.raises(ValidationError):
        _settings(analysis_max_concurrent_per_user=0)

    with pytest.raises(ValidationError):
        _settings(analysis_task_max_retries=-1)


def test_non_local_requires_broker_and_result_backend() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="postgresql+asyncpg://u:p@db:5432/db",
            redis_url="redis://redis:6379/0",
            security_hash_secret="s" * 32,
            jwt_secret="j" * 32,
            google_client_id="id",
            google_client_secret="secret",
            google_redirect_uri="https://example.test/callback",
            frontend_url="https://example.test",
            s3_bucket="bucket",
            s3_access_key_id="key",
            s3_secret_access_key="secret",
            rabbitmq_url="",
            celery_result_backend="",
        )
