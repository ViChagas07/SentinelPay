import logging
from collections.abc import Mapping
from typing import Any

from opentelemetry import trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from paysentineliq.application.security.redaction import mask_pii
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.logging import get_request_id
from paysentineliq.infrastructure.observability import celery as celery_signals

_logger = logging.getLogger("paysentineliq")
_OTLP_LOGGER = "opentelemetry.exporter.otlp.proto.http.trace_exporter"
_REDACTED = "[REDACTED]"
_MAX_STRING = 256
_MAX_STATEMENT = 512

_DROPPED_KEYS = frozenset(
    {
        "http.url",
        "http.target",
        "url.full",
        "url.path",
        "url.query",
        "http.request.body",
        "http.response.body",
        "body",
        "payload",
        "document.text",
        "document_text",
        "prompt",
        "messages",
        "response",
        "content",
        "user.id",
        "enduser.id",
        "user_id",
        "owner_id",
        "document_id",
        "analysis_id",
        "payable_id",
        "notification_id",
        "exception.stacktrace",
        "net.peer.ip",
        "net.sock.peer.addr",
        "http.client_ip",
        "client.address",
    },
)
_SENSITIVE_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "email",
    "cpf",
    "cnpj",
    "phone",
    "document",
    "prompt",
    "salary",
    "address",
)

_provider: TracerProvider | None = None
_configured = False
_libraries_instrumented = False
_sqlalchemy_instrumented: set[int] = set()


class PiiSanitizingSpanProcessor(SpanProcessor):
    def __init__(self, delegate: SpanProcessor) -> None:
        self._delegate = delegate

    def on_start(
        self,
        span: Span,
        parent_context: Any = None,
    ) -> None:
        sanitize_span(span)
        self._delegate.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        sanitize_readable_span(span)
        self._delegate.on_end(span)

    def shutdown(self) -> None:
        self._delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return self._delegate.force_flush(timeout_millis)


def sanitize_span(span: Span) -> None:
    for key, value in dict(span.attributes or {}).items():
        span.set_attribute(key, _sanitize_attribute(key, value))
    request_id = get_request_id()
    if request_id:
        span.set_attribute("request_id", request_id)
    span.update_name(_safe_name(span.name))


def sanitize_readable_span(span: ReadableSpan) -> None:
    attributes = getattr(span, "_attributes", None)
    if isinstance(attributes, Mapping):
        span._attributes = {
            key: _sanitize_attribute(key, value) for key, value in attributes.items()
        }
    events = getattr(span, "_events", ())
    for event in events or ():
        event_attributes = getattr(event, "_attributes", None)
        if isinstance(event_attributes, Mapping):
            event._attributes = {
                key: _sanitize_attribute(key, value) for key, value in event_attributes.items()
            }
        event_name = getattr(event, "_name", "")
        if isinstance(event_name, str):
            event._name = _safe_name(event_name)
    status = getattr(span, "_status", None)
    if status is not None and getattr(status, "description", None):
        span._status = Status(StatusCode(status.status_code))
    name = getattr(span, "_name", "")
    if isinstance(name, str):
        span._name = _safe_name(name)


def _sanitize_attribute(key: str, value: Any) -> Any:
    normalized_key = key.lower()
    if normalized_key == "request_id":
        return _sanitize_value(value)
    if normalized_key.startswith("http.request.header.") or normalized_key.startswith(
        "http.response.header.",
    ):
        return _REDACTED
    if normalized_key in _DROPPED_KEYS:
        return _REDACTED
    if any(fragment in normalized_key for fragment in _SENSITIVE_FRAGMENTS):
        return _REDACTED
    if normalized_key == "db.statement":
        return _sanitize_value(value, limit=_MAX_STATEMENT)
    return _sanitize_value(value)


def _sanitize_value(value: Any, *, limit: int = _MAX_STRING) -> Any:
    if isinstance(value, str):
        return mask_pii(value)[:limit]
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return type(value)(_sanitize_value(item, limit=limit) for item in value)
    if isinstance(value, Mapping):
        return {str(key)[:64]: _sanitize_value(item, limit=limit) for key, item in value.items()}
    if isinstance(value, bytes):
        return _REDACTED
    return mask_pii(str(value))[:limit]


def _safe_name(value: str) -> str:
    return mask_pii(value)[:256]


def build_resource(settings: Settings) -> Resource:
    return Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.otel_service_version,
            "deployment.environment": settings.app_env,
        },
    )


def create_otlp_exporter(settings: Settings) -> OTLPSpanExporter:
    endpoint = settings.otel_exporter_otlp_endpoint.strip()
    if endpoint.endswith("/"):
        endpoint = endpoint[:-1]
    if not endpoint.endswith("/v1/traces"):
        endpoint = f"{endpoint}/v1/traces"
    return OTLPSpanExporter(
        endpoint=endpoint,
        timeout=settings.otel_exporter_timeout_seconds,
    )


def build_tracer_provider(
    settings: Settings,
    *,
    span_exporter: SpanExporter | None = None,
) -> TracerProvider | None:
    if settings.otel_sdk_disabled:
        return None
    endpoint = settings.otel_exporter_otlp_endpoint.strip()
    if not endpoint:
        return None
    exporter = span_exporter or create_otlp_exporter(settings)
    sampler = ParentBased(TraceIdRatioBased(settings.otel_traces_sampler_ratio))
    provider = TracerProvider(resource=build_resource(settings), sampler=sampler)
    provider.add_span_processor(
        PiiSanitizingSpanProcessor(BatchSpanProcessor(exporter)),
    )
    return provider


def configure_tracing(
    settings: Settings,
    *,
    instrument_libraries: bool = True,
) -> bool:
    global _configured, _provider
    if _configured:
        return _provider is not None
    if settings.otel_sdk_disabled:
        _configured = True
        return False
    provider = build_tracer_provider(settings)
    if provider is None:
        _configured = True
        return False
    trace.set_tracer_provider(provider)
    set_global_textmap(
        CompositePropagator(
            [TraceContextTextMapPropagator(), W3CBaggagePropagator()],
        ),
    )
    if settings.app_env == "local":
        logging.getLogger(_OTLP_LOGGER).setLevel(logging.CRITICAL)
    _provider = provider
    _configured = True
    if instrument_libraries:
        instrument_library_clients()
    _logger.info("otel_tracing_enabled")
    return True


def instrument_library_clients() -> None:
    global _libraries_instrumented
    if _libraries_instrumented:
        return
    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]
    celery_signals.connect_celery_signals()
    _libraries_instrumented = True


def instrument_fastapi_app(app: Any, settings: Settings) -> None:
    if not _configured or _provider is None:
        return
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/metrics,/health,/ready,/docs,/redoc,/openapi.json",
    )


def instrument_sqlalchemy_engine(
    engine: Any,
    *,
    enabled: bool | None = None,
) -> None:
    if enabled is None:
        enabled = _configured and _provider is not None
    if not enabled:
        return
    identifier = id(engine)
    if identifier in _sqlalchemy_instrumented:
        return
    from sqlalchemy import event

    tracer = trace.get_tracer("paysentineliq")

    def before_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        span = tracer.start_span("sql.query")
        operation = statement.lstrip().split(None, 1)[0].upper() if statement else "SQL"
        span.set_attribute("db.system.name", "postgresql")
        span.set_attribute("db.operation", operation[:16])
        span.set_attribute("db.executemany", bool(executemany))
        context._otel_span = span

    def after_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        span = getattr(context, "_otel_span", None)
        if span is not None:
            span.set_status(Status(StatusCode.OK))
            span.end()
            context._otel_span = None

    def handle_error(exception_context: Any) -> None:
        context = getattr(exception_context, "execution_context", None)
        span = getattr(context, "_otel_span", None) if context is not None else None
        if context is not None and span is not None:
            span.set_status(Status(StatusCode.ERROR))
            span.end()
            context._otel_span = None

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    event.listen(engine, "after_cursor_execute", after_cursor_execute)
    event.listen(engine, "handle_error", handle_error)
    _sqlalchemy_instrumented.add(identifier)


def reset_tracing_for_tests() -> None:
    global _configured, _provider
    _configured = False
    _provider = None
