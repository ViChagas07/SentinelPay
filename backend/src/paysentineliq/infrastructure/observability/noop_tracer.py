from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from paysentineliq.domain.ports.observability import (
    ObservationHandle,
    ObservationLevel,
    ObservationType,
    ScoreDataType,
)


class _NoopObservation:
    def update(
        self,
        *,
        output: Any = None,
        metadata: Mapping[str, Any] | None = None,
        level: ObservationLevel | None = None,
        status_message: str | None = None,
    ) -> None:
        return None


_NOOP_OBSERVATION = _NoopObservation()


class NoopTracer:
    @contextmanager
    def trace(
        self,
        name: str,
        *,
        session_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        tags: Sequence[str] = (),
        environment: str | None = None,
        input: Any = None,
    ) -> Iterator[ObservationHandle]:
        yield _NOOP_OBSERVATION

    @contextmanager
    def observation(
        self,
        name: str,
        *,
        as_type: ObservationType = "generation",
        input: Any = None,
        metadata: Mapping[str, Any] | None = None,
        model: str | None = None,
    ) -> Iterator[ObservationHandle]:
        yield _NOOP_OBSERVATION

    def score(
        self,
        name: str,
        value: float | str,
        *,
        data_type: ScoreDataType | None = None,
        comment: str | None = None,
    ) -> None:
        return None

    def current_trace_id(self) -> str | None:
        return None

    async def flush(self) -> None:
        return None

    async def aclose(self) -> None:
        return None
