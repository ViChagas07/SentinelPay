import base64
import binascii
import json
from datetime import date
from uuid import UUID

from paysentineliq.application.errors import InvalidCursorError


def encode_payable_cursor(due_date: date, payable_id: UUID) -> str:
    payload = json.dumps(
        {"due_date": due_date.isoformat(), "id": str(payable_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_payable_cursor(value: str) -> tuple[date, UUID]:
    if not value.strip():
        raise InvalidCursorError()
    padding = "=" * (-len(value) % 4)
    try:
        raw = base64.urlsafe_b64decode(f"{value}{padding}")
        payload: object = json.loads(raw)
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidCursorError() from exc
    if not isinstance(payload, dict):
        raise InvalidCursorError()
    due_date = payload.get("due_date")
    payable_id = payload.get("id")
    if not isinstance(due_date, str) or not isinstance(payable_id, str):
        raise InvalidCursorError()
    try:
        parsed_date = date.fromisoformat(due_date)
        parsed_id = UUID(payable_id)
    except (ValueError, TypeError) as exc:
        raise InvalidCursorError() from exc
    return parsed_date, parsed_id
