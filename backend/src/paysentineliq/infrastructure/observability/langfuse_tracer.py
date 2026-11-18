import asyncio
import logging
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Protocol, cast

from paysentineliq.application.security.observability_masking import ObservabilityMasker
from paysentineliq.domain.ports.observability import (
    ObservabilityTracer,
    ObservationHandle,
    ObservationLevel,
    ObservationType,
    ScoreDataType,
)
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.observability.noop_tracer import NoopTracer

_LOGGER = logging.getLogger("paysentineliq")
_CLIENT_TIMEOUT_SECONDS = 2
_FLUSH_AT = 10
_FLUSH_INTERVAL_SECONDS = 2.0
_SHUTDOWN_TIMEOUT_SECONDS = 2.0
_DEFAULT_HOST = "https://cloud.langfuse.com"

PropagateFactory = Callable[..., AbstractContextManager[Any]]


def _default_propagate(**kwargs: Any) -> AbstractContextManager[Any]:
    from langfuse import propagate_attributes

    return propagate_attributes(**kwargs)


class LangfuseClientPort(Protocol):
    def start_as_current_observation(
        self,
        *,
        name: str,
        as_type: ObservationType = "generation",
        input: Any = None,
        metadata: Any = None,
        model: str | None = None,
    ) -> AbstractContextManager[Any]: ...

    def score_current_trace(
        self,
        *,
        name: str,
        value: float | str,
        data_type: ScoreDataType | None = None,
        comment: str | None = None,
    ) -> None: ...

    def get_current_trace_id(self) -> str | None: ...

    def flush(self) -> None: ...

    def shutdown(self) -> None: ...


class _LangfuseObservation:
    def __init__(self, span: Any, masker: ObservabilityMasker) -> None:
        self._span = span
        self._masker = masker

    def update(
        self,
        *,
        output: Any = None,
        metadata: Mapping[str, Any] | None = None,
        level: ObservationLevel | None = None,
        status_message: str | None = None,
    ) -> None:
        try:
            values: dict[str, Any] = {}
            if output is not None:
                values["output"] = self._masker.mask_payload(output)
            if metadata is not None:
                values["metadata"] = self._masker.mask_payload(metadata)
            if level is not None:
                values["level"] = level
            if status_message is not None:
                values["status_message"] = self._masker.mask_text(status_message)
            if values:
                self._span.update(**values)
        except Exception:
            _LOGGER.warning("langfuse_observation_update_failed")


class LangfuseTracer:
    def __init__(
        self,
        client: LangfuseClientPort,
        masker: ObservabilityMasker,
        *,
        propagate: PropagateFactory | None = None,
    ) -> None:
        self._client = client
        self._masker = masker
        self._propagate = propagate or _default_propagate

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
        try:
            masked_metadata = self._masker.mask_payload(metadata) if metadata is not None else None
            masked_input = self._masker.mask_payload(input) if input is not None else None
        except Exception:
            _LOGGER.warning("langfuse_masking_failed")
            with NoopTracer().trace(name) as handle:
                yield handle
            return
        try:
            attributes = self._propagate(
                session_id=session_id,
                metadata=masked_metadata,
                tags=list(tags),
                trace_name=name,
                environment=environment,
            )
        except Exception:
            _LOGGER.warning("langfuse_trace_start_failed")
            with NoopTracer().trace(name) as handle:
                yield handle
            return
        user_error: BaseException | None = None
        yielded = False
        try:
            with (
                attributes,
                self.observation(
                    name,
                    as_type="span",
                    input=masked_input,
                    metadata=masked_metadata,
                ) as handle,
            ):
                try:
                    yielded = True
                    yield handle
                except BaseException as error:
                    user_error = error
                    handle.update(level="ERROR", status_message=type(error).__name__)
                    raise
        except Exception:
            if user_error is not None:
                raise user_error from None
            _LOGGER.warning("langfuse_trace_failed")
            if not yielded:
                with NoopTracer().trace(name) as handle:
                    yield handle

    def score(
        self,
        name: str,
        value: float | str,
        *,
        data_type: ScoreDataType | None = None,
        comment: str | None = None,
    ) -> None:
        try:
            safe_value = self._masker.mask_text(value) if isinstance(value, str) else value
            safe_comment = self._masker.mask_text(comment) if comment is not None else None
            self._client.score_current_trace(
                name=name,
                value=safe_value,
                data_type=data_type,
                comment=safe_comment,
            )
        except Exception:
            _LOGGER.warning("langfuse_score_failed")

    def current_trace_id(self) -> str | None:
        try:
            return self._client.get_current_trace_id()
        except Exception:
            _LOGGER.warning("langfuse_current_trace_id_failed")
            return None

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
        try:
            masked_input = self._masker.mask_payload(input) if input is not None else None
            masked_metadata = self._masker.mask_payload(metadata) if metadata is not None else None
        except Exception:
            _LOGGER.warning("langfuse_masking_failed")
            with NoopTracer().observation(name, as_type=as_type) as handle:
                yield handle
            return
        try:
            manager = self._client.start_as_current_observation(
                name=name,
                as_type=as_type,
                input=masked_input,
                metadata=masked_metadata,
                model=model,
            )
        except Exception:
            _LOGGER.warning("langfuse_observation_start_failed")
            with NoopTracer().observation(name, as_type=as_type) as handle:
                yield handle
            return
        user_error: BaseException | None = None
        yielded = False
        try:
            with manager as span:
                handle = _LangfuseObservation(span, self._masker)
                try:
                    yielded = True
                    yield handle
                except BaseException as error:
                    user_error = error
                    handle.update(level="ERROR", status_message=type(error).__name__)
                    raise
        except Exception:
            if user_error is not None:
                raise user_error from None
            _LOGGER.warning("langfuse_observation_failed")
            if not yielded:
                with NoopTracer().observation(name, as_type=as_type) as handle:
                    yield handle

    async def flush(self) -> None:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._client.flush),
                timeout=_SHUTDOWN_TIMEOUT_SECONDS,
            )
        except Exception:
            _LOGGER.warning("langfuse_flush_failed")

    async def aclose(self) -> None:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._client.shutdown),
                timeout=_SHUTDOWN_TIMEOUT_SECONDS,
            )
        except Exception:
            _LOGGER.warning("langfuse_shutdown_failed")


def build_observability_tracer(settings: Settings) -> ObservabilityTracer:
    if not settings.langfuse_enabled:
        return NoopTracer()
    public_key = settings.langfuse_public_key.strip()
    secret_key = settings.langfuse_secret_key.strip()
    if not public_key or not secret_key:
        _LOGGER.warning("langfuse_disabled_missing_keys")
        return NoopTracer()
    masker = ObservabilityMasker(hash_secret=settings.security_hash_secret)
    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            base_url=(
                settings.langfuse_host.strip()
                or settings.langfuse_base_url.strip()
                or _DEFAULT_HOST
            ),
            timeout=_CLIENT_TIMEOUT_SECONDS,
            flush_at=_FLUSH_AT,
            flush_interval=_FLUSH_INTERVAL_SECONDS,
            environment=settings.app_env,
            sample_rate=settings.langfuse_sample_rate,
            mask=masker.mask_for_langfuse,
        )
    except Exception:
        _LOGGER.warning("langfuse_init_failed")
        return NoopTracer()
    return LangfuseTracer(cast(LangfuseClientPort, client), masker)
