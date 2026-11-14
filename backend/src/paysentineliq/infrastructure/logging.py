import json
import logging
import re
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime

from paysentineliq.infrastructure.config import Settings

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="")

_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")
_BEARER_RE = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}")
_SECRET_RE = re.compile(
    r"(?i)\b(token|api[_-]?key|secret|password)\b\s*[=:]\s*[\"']?[^\s\"',;]{4,}"
)
_AWS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_CNPJ_RE = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_CPF_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}[-\s]?\d{4}(?!\w)")

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


def mask_pii(value: str) -> str:
    masked = _JWT_RE.sub("[REDACTED_JWT]", value)
    masked = _BEARER_RE.sub(r"\1 [REDACTED_TOKEN]", masked)
    masked = _SECRET_RE.sub(r"\1=[REDACTED]", masked)
    masked = _AWS_KEY_RE.sub("[REDACTED_AWS_KEY]", masked)
    masked = _CNPJ_RE.sub("[REDACTED_CNPJ]", masked)
    masked = _CPF_RE.sub("[REDACTED_CPF]", masked)
    masked = _EMAIL_RE.sub("[REDACTED_EMAIL]", masked)
    return _PHONE_RE.sub("[REDACTED_PHONE]", masked)


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
