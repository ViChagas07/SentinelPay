from typing import Any
from uuid import UUID

import pytest

from paysentineliq.infrastructure.logging import get_request_id, reset_request_id, set_request_id
from paysentineliq.infrastructure.messaging.dispatcher import CeleryTaskDispatcher
from paysentineliq.infrastructure.observability import celery as celery_tracing

pytestmark = pytest.mark.unit


class FakeCeleryApp:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def send_task(self, name: str, **kwargs: Any) -> None:
        self.calls.append({"name": name, **kwargs})


class FakeRequest:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {}


class FakeTask:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.request = FakeRequest(headers)


def test_dispatcher_propagates_request_id_header() -> None:
    app = FakeCeleryApp()
    dispatcher = CeleryTaskDispatcher(app)
    token = set_request_id("req-abc")
    try:
        dispatcher.dispatch_analysis(UUID("123e4567-e89b-12d3-a456-426614174000"))
        dispatcher.dispatch_notification(UUID("223e4567-e89b-12d3-a456-426614174000"))
    finally:
        reset_request_id(token)

    assert app.calls[0]["headers"] == {"request_id": "req-abc"}
    assert app.calls[1]["headers"] == {"request_id": "req-abc"}


def test_dispatcher_generates_request_id_when_missing() -> None:
    app = FakeCeleryApp()
    dispatcher = CeleryTaskDispatcher(app)

    dispatcher.dispatch_analysis(UUID("123e4567-e89b-12d3-a456-426614174000"))

    request_id = app.calls[0]["headers"]["request_id"]
    assert isinstance(request_id, str)
    assert len(request_id) >= 16


def test_task_prerun_restores_safe_request_id_and_postrun_clears_it() -> None:
    task = FakeTask({"request_id": "req-worker-1"})

    token = celery_tracing.set_task_request_id("task-1", task)
    restored = get_request_id()
    celery_tracing.clear_task_request_id("task-1", token)

    assert restored == "req-worker-1"
    assert get_request_id() == ""


def test_task_prerun_generates_id_for_invalid_header() -> None:
    task = FakeTask({"request_id": "bad id with spaces\n"})

    token = celery_tracing.set_task_request_id("task-2", task)
    generated = get_request_id()
    celery_tracing.clear_task_request_id("task-2", token)

    assert generated
    assert " " not in generated
    assert "\n" not in generated


def test_task_prerun_and_postrun_are_idempotent() -> None:
    task = FakeTask({"request_id": "req-worker-2"})

    token = celery_tracing.set_task_request_id("task-3", task)
    celery_tracing.clear_task_request_id("task-3", token)
    celery_tracing.clear_task_request_id("task-3", None)

    assert get_request_id() == ""
