import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime

from paysentineliq.application.security.redaction import mask_pii as mask_pii
from paysentineliq.infrastructure.config import Settings

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="")

_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def set_request_id(value: str) -> Token[str]:
    return _REQUEST_ID.set(value)


def reset_request_id(token: Token[str]) -> None:
    _REQUEST_ID.reset(token)


def get_request_id() -> str:
    return _REQUEST_ID.get()


class PIIMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        masked = mask_pii(message)
        if masked != message:
            record.msg = masked
            record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id
        for key in (
            "event",
            "analysis_id",
            "otel_trace_id",
            "langfuse_trace_id",
        ):
            value = getattr(record, key, None)
            if value:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(settings: Settings) -> None:
    logger = logging.getLogger("paysentineliq")
    logger.setLevel(_LEVELS.get(settings.log_level.upper(), logging.INFO))
    logger.propagate = False

    if any(isinstance(handler.formatter, JsonFormatter) for handler in logger.handlers):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(PIIMaskingFilter())
    logger.addHandler(handler)
