from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from typing import Any, Literal, Protocol

ObservationType = Literal[
    "generation",
    "span",
    "embedding",
    "retriever",
    "tool",
    "chain",
    "agent",
    "guardrail",
    "evaluator",
]
ObservationLevel = Literal["DEBUG", "DEFAULT", "WARNING", "ERROR"]
ScoreDataType = Literal["NUMERIC", "CATEGORICAL", "BOOLEAN", "TEXT", "CORRECTION"]


class ObservationHandle(Protocol):
    def update(
        self,
        *,
        output: Any = None,
        metadata: Mapping[str, Any] | None = None,
        level: ObservationLevel | None = None,
        status_message: str | None = None,
    ) -> None: ...


class ObservabilityTracer(Protocol):
    def trace(
        self,
        name: str,
        *,
        session_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        tags: Sequence[str] = (),
        environment: str | None = None,
        input: Any = None,
    ) -> AbstractContextManager[ObservationHandle]: ...

    def observation(
        self,
        name: str,
        *,
        as_type: ObservationType = "generation",
        input: Any = None,
        metadata: Mapping[str, Any] | None = None,
        model: str | None = None,
    ) -> AbstractContextManager[ObservationHandle]: ...

    def score(
        self,
        name: str,
        value: float | str,
        *,
        data_type: ScoreDataType | None = None,
        comment: str | None = None,
    ) -> None: ...

    def current_trace_id(self) -> str | None: ...

    async def flush(self) -> None: ...

    async def aclose(self) -> None: ...
