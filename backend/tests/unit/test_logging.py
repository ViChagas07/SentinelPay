import json
import logging

import pytest

from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.logging import (
    JsonFormatter,
    PIIMaskingFilter,
    configure_logging,
    mask_pii,
    reset_request_id,
    set_request_id,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("cpf 123.456.789-00", "cpf [REDACTED_CPF]"),
        ("cnpj 12.345.678/0001-90", "cnpj [REDACTED_CNPJ]"),
        ("email demo@example.com", "email [REDACTED_EMAIL]"),
        ("telefone (11) 98765-4321", "telefone [REDACTED_PHONE]"),
        ("telefone +55 11 98765-4321", "telefone [REDACTED_PHONE]"),
        ("Bearer abcdefghijklmnop", "Bearer [REDACTED_TOKEN]"),
        (
            "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
            "jwt [REDACTED_JWT]",
        ),
        ("api_key=supersecret123", "api_key=[REDACTED]"),
        ("credencial AKIAIOSFODNN7EXAMPLE", "credencial [REDACTED_AWS_KEY]"),
        ("request_id=abc-123 status=200", "request_id=abc-123 status=200"),
        (
            "550e8400-e29b-41d4-a716-446655440000",
            "550e8400-e29b-41d4-a716-446655440000",
        ),
        (
            "00000000-0000-0000-0000-000000000000",
            "00000000-0000-0000-0000-000000000000",
        ),
    ],
)
def test_mask_pii(raw: str, expected: str) -> None:
    assert mask_pii(raw) == expected


def test_filter_masks_message_with_args() -> None:
    record = logging.LogRecord(
        name="paysentineliq",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="email=%s cpf=%s",
        args=("demo@example.com", "123.456.789-00"),
        exc_info=None,
    )

    PIIMaskingFilter().filter(record)

    message = record.getMessage()
    assert "demo@example.com" not in message
    assert "123.456.789-00" not in message
    assert "[REDACTED_EMAIL]" in message
    assert "[REDACTED_CPF]" in message


def test_json_formatter_includes_request_id_and_masks() -> None:
    token = set_request_id("req-test-1")
    try:
        record = logging.LogRecord(
            name="paysentineliq",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="email=%s",
            args=("demo@example.com",),
            exc_info=None,
        )
        PIIMaskingFilter().filter(record)

        payload = json.loads(JsonFormatter().format(record))
    finally:
        reset_request_id(token)

    assert payload["level"] == "INFO"
    assert payload["request_id"] == "req-test-1"
    assert "demo@example.com" not in payload["message"]
    assert "[REDACTED_EMAIL]" in payload["message"]


def test_configure_logging_is_idempotent() -> None:
    settings = Settings(app_env="local")

    configure_logging(settings)
    configure_logging(settings)

    handlers = [
        handler
        for handler in logging.getLogger("paysentineliq").handlers
        if isinstance(handler.formatter, JsonFormatter)
    ]
    assert len(handlers) == 1


def test_json_formatter_includes_trace_correlation_ids() -> None:
    record = logging.LogRecord(
        name="paysentineliq",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="analysis_trace",
        args=(),
        exc_info=None,
    )
    record.event = "analysis_trace"
    record.analysis_id = "analysis-1"
    record.otel_trace_id = "0" * 32
    record.langfuse_trace_id = "langfuse-trace-1"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "analysis_trace"
    assert payload["analysis_id"] == "analysis-1"
    assert payload["otel_trace_id"] == "0" * 32
    assert payload["langfuse_trace_id"] == "langfuse-trace-1"
