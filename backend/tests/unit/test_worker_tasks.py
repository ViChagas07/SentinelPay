from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from paysentineliq.application.commands.process_analysis import ProcessedAnalysis
from paysentineliq.application.errors import StorageNotConfiguredError
from paysentineliq.infrastructure.composition.analysis_worker import build_worker_runtime
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.messaging import tasks
from paysentineliq.infrastructure.messaging.celery_app import celery_app

pytestmark = pytest.mark.unit


class FakeDispatcher:
    def __init__(self) -> None:
        self.notifications: list[UUID] = []

    def dispatch_analysis(self, analysis_id: UUID, *, locale: str = "pt") -> None:
        return None

    def dispatch_notification(self, notification_id: UUID) -> None:
        self.notifications.append(notification_id)


def test_eager_analysis_task_dispatches_pending_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notification_id = uuid4()
    executed: list[dict[str, object]] = []

    async def fake_execute(
        analysis_id: UUID,
        *,
        task_id: str,
        attempt: int,
        final_attempt: bool,
        locale: str,
    ) -> ProcessedAnalysis:
        executed.append(
            {
                "analysis_id": analysis_id,
                "task_id": task_id,
                "attempt": attempt,
                "final_attempt": final_attempt,
                "locale": locale,
            },
        )
        return ProcessedAnalysis(
            analysis_id=analysis_id,
            status="completed",
            notification_ids=(notification_id,),
        )

    dispatcher = FakeDispatcher()
    monkeypatch.setattr(tasks, "_execute_analysis", fake_execute)
    monkeypatch.setattr(tasks, "CeleryTaskDispatcher", lambda app: dispatcher)
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    try:
        analysis_id = uuid4()
        result = tasks.run_analysis_task.delay(str(analysis_id), "pt").get(timeout=5)
    finally:
        celery_app.conf.task_always_eager = False
        celery_app.conf.task_eager_propagates = False

    assert result == {"status": "completed"}
    assert executed[0]["analysis_id"] == analysis_id
    assert executed[0]["attempt"] == 1
    assert executed[0]["final_attempt"] is False
    assert executed[0]["locale"] == "pt"
    assert dispatcher.notifications == [notification_id]


def test_notification_task_is_a_pending_placeholder() -> None:
    assert tasks.dispatch_notification.run(str(uuid4())) == "pending"
    assert tasks.dispatch_notification.run("invalid") == "discarded"


def test_sweep_task_returns_count(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_sweep() -> int:
        return 2

    monkeypatch.setattr(tasks, "_sweep_stale_analyses", fake_sweep)

    assert tasks.sweep_stale_analyses.run() == 2


async def test_worker_runtime_requires_storage() -> None:
    settings = Settings(
        app_env="local",
        rabbitmq_url="memory://",
        celery_result_backend="cache+memory://",
    )

    with pytest.raises(StorageNotConfiguredError):
        async with build_worker_runtime(settings):
            pass


async def test_worker_runtime_builds_and_disposes_with_null_pool() -> None:
    settings = Settings(
        app_env="local",
        database_url="postgresql+asyncpg://user:pass@localhost:55432/db",
        rabbitmq_url="memory://",
        celery_result_backend="cache+memory://",
        s3_access_key_id="key",
        s3_secret_access_key="secret",
        s3_bucket="bucket",
        fraud_model_dir="missing-artifacts",
    )

    async with build_worker_runtime(settings) as handler:
        assert handler is not None
        assert datetime.now(UTC).tzinfo is not None
