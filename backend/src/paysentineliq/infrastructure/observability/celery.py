import contextlib
import re
from collections.abc import Mapping
from contextvars import Token
from typing import Any
from uuid import uuid4

from celery.signals import task_postrun, task_prerun
from opentelemetry import trace

from paysentineliq.infrastructure.logging import (
    reset_request_id,
    set_request_id,
)

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_tokens: dict[str, Token[str]] = {}
_connected = False


def set_task_request_id(task_id: str, task: Any) -> Token[str] | None:
    request_id = _request_id_from_task(task) or str(uuid4())
    token = set_request_id(request_id)
    _tokens[task_id] = token
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute("request_id", request_id)
    return token


def clear_task_request_id(
    task_id: str,
    token: Token[str] | None = None,
) -> None:
    stored = _tokens.pop(task_id, None) or token
    if stored is None:
        return
    with contextlib.suppress(ValueError):
        reset_request_id(stored)


def _request_id_from_task(task: Any) -> str:
    request = getattr(task, "request", None)
    headers = getattr(request, "headers", None)
    candidate: Any = None
    if isinstance(headers, Mapping):
        candidate = headers.get("request_id")
    if not isinstance(candidate, str):
        candidate = getattr(request, "request_id", None)
    if isinstance(candidate, str) and _SAFE_REQUEST_ID.fullmatch(candidate):
        return candidate
    return ""


def _on_task_prerun(
    task_id: str | None = None,
    task: Any = None,
    **kwargs: Any,
) -> None:
    if task_id and task is not None:
        set_task_request_id(str(task_id), task)


def _on_task_postrun(task_id: str | None = None, **kwargs: Any) -> None:
    if task_id:
        clear_task_request_id(str(task_id))


def connect_celery_signals() -> None:
    global _connected
    if _connected:
        return
    task_prerun.connect(_on_task_prerun, weak=False)
    task_postrun.connect(_on_task_postrun, weak=False)
    _connected = True
