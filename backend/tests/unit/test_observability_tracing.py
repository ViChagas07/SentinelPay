from collections.abc import Iterator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Status, StatusCode
from sqlalchemy import create_engine, text

from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.logging import reset_request_id, set_request_id
from paysentineliq.infrastructure.observability import tracing
from paysentineliq.infrastructure.observability.tracing import (
    PiiSanitizingSpanProcessor,
)

pytestmark = pytest.mark.unit

_CPF = "529.982.247-25"
_EMAIL = "user@example.com"
_PHONE = "+5511999999999"
_DOCUMENT_TEXT = "texto integral do documento"


@pytest.fixture
def exported_spans() -> Iterator[InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(
        PiiSanitizingSpanProcessor(SimpleSpanProcessor(exporter)),
    )
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.clear()


def test_sanitizer_redacts_pii_headers_urls_and_exception_events(
    exported_spans: InMemorySpanExporter,
) -> None:
    token = set_request_id("req-123")
    try:
        tracer = trace.get_tracer("paysentineliq")
        with tracer.start_as_current_span(f"span {_EMAIL}") as span:
            span.set_attribute("user.email", _EMAIL)
            span.set_attribute("cpf", _CPF)
            span.set_attribute("phone", _PHONE)
            span.set_attribute("document.text", _DOCUMENT_TEXT)
            span.set_attribute("http.target", f"/api/v1/x?email={_EMAIL}")
            span.set_attribute("http.request.header.authorization", "Bearer secret")
            span.set_attribute("net.peer.ip", "203.0.113.10")
            span.set_attribute("safe.attribute", "ok")
            span.record_exception(ValueError(f"falha para {_EMAIL}"))
            span.set_status(Status(StatusCode.ERROR, f"erro de {_EMAIL}"))
    finally:
        reset_request_id(token)

    spans = exported_spans.get_finished_spans()
    assert len(spans) == 1
    readable = spans[0]
    attributes = dict(readable.attributes or {})
    dumped = repr(attributes)

    assert attributes["user.email"] == "[REDACTED]"
    assert attributes["cpf"] == "[REDACTED]"
    assert attributes["phone"] == "[REDACTED]"
    assert attributes["document.text"] == "[REDACTED]"
    assert attributes["http.target"] == "[REDACTED]"
    assert attributes["http.request.header.authorization"] == "[REDACTED]"
    assert attributes["net.peer.ip"] == "[REDACTED]"
    assert attributes["safe.attribute"] == "ok"
    assert attributes["request_id"] == "req-123"
    assert _EMAIL not in dumped
    assert _CPF not in dumped
    assert _PHONE not in dumped
    assert _DOCUMENT_TEXT not in dumped
    assert _EMAIL not in readable.name
    assert readable.status.description is None

    event_dump = repr(
        [(event.name, dict(event.attributes or {})) for event in readable.events],
    )
    assert _EMAIL not in event_dump
    assert _CPF not in event_dump
    assert _PHONE not in event_dump


def test_sqlalchemy_spans_have_operation_but_no_statement_or_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(
        PiiSanitizingSpanProcessor(SimpleSpanProcessor(exporter)),
    )
    monkeypatch.setattr(trace, "get_tracer", provider.get_tracer)
    engine = create_engine("sqlite://")

    tracing.instrument_sqlalchemy_engine(engine, enabled=True)
    with engine.connect() as connection:
        connection.execute(text("SELECT 42 AS secret_value"))

    spans = [span for span in exporter.get_finished_spans() if span.name == "sql.query"]
    assert spans
    attributes = dict(spans[0].attributes or {})
    dumped = repr(attributes)
    assert attributes["db.system.name"] == "postgresql"
    assert attributes["db.operation"] == "SELECT"
    assert "SELECT 42" not in dumped
    assert "secret_value" not in dumped


def test_configure_tracing_is_disabled_by_default() -> None:
    settings = Settings(app_env="local")

    assert tracing.configure_tracing(settings, instrument_libraries=False) is False


def test_otel_exporter_uses_endpoint_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeOtlpExporter:
        def __init__(self, *, endpoint: str, timeout: float) -> None:
            captured["endpoint"] = endpoint
            captured["timeout"] = timeout

    monkeypatch.setattr(tracing, "OTLPSpanExporter", FakeOtlpExporter)
    settings = Settings(
        app_env="local",
        otel_sdk_disabled=False,
        otel_exporter_otlp_endpoint="http://collector:4318",
        otel_exporter_timeout_seconds=3.5,
    )

    exporter = tracing.create_otlp_exporter(settings)

    assert isinstance(exporter, FakeOtlpExporter)
    assert captured == {
        "endpoint": "http://collector:4318/v1/traces",
        "timeout": 3.5,
    }


def test_otlp_exporter_keeps_full_traces_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeOtlpExporter:
        def __init__(self, *, endpoint: str, timeout: float) -> None:
            captured["endpoint"] = endpoint

    monkeypatch.setattr(tracing, "OTLPSpanExporter", FakeOtlpExporter)
    settings = Settings(
        app_env="local",
        otel_sdk_disabled=False,
        otel_exporter_otlp_endpoint="http://collector:4318/v1/traces/",
    )

    tracing.create_otlp_exporter(settings)

    assert captured["endpoint"] == "http://collector:4318/v1/traces"


def test_sampler_ratio_is_applied() -> None:
    settings = Settings(
        app_env="local",
        otel_sdk_disabled=False,
        otel_exporter_otlp_endpoint="http://collector:4318",
        otel_traces_sampler_ratio=0.0,
    )

    provider = tracing.build_tracer_provider(
        settings,
        span_exporter=InMemorySpanExporter(),
    )

    assert provider is not None
    assert provider.sampler is not None


def test_settings_require_endpoint_when_sdk_is_enabled() -> None:
    with pytest.raises(ValueError, match="OTEL_EXPORTER_OTLP_ENDPOINT"):
        Settings(app_env="local", otel_sdk_disabled=False)


def test_resource_has_service_name_and_environment() -> None:
    settings = Settings(
        app_env="local",
        otel_sdk_disabled=False,
        otel_exporter_otlp_endpoint="http://collector:4318",
        otel_service_name="paysentineliq-worker",
    )

    resource = tracing.build_resource(settings)

    assert resource.attributes["service.name"] == "paysentineliq-worker"
    assert resource.attributes["deployment.environment"] == "local"
    assert "service.version" in resource.attributes
