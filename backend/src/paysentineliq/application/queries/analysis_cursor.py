import base64
import binascii
import json
from datetime import UTC, datetime
from uuid import UUID

from paysentineliq.application.errors import InvalidCursorError


def encode_cursor(created_at: datetime, analysis_id: UUID) -> str:
    payload = json.dumps(
        {
            "created_at": created_at.astimezone(UTC).isoformat(),
            "id": str(analysis_id),
        },
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, UUID]:
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
    created_at = payload.get("created_at")
    analysis_id = payload.get("id")
    if not isinstance(created_at, str) or not isinstance(analysis_id, str):
        raise InvalidCursorError()
    try:
        parsed_time = datetime.fromisoformat(created_at)
        parsed_id = UUID(analysis_id)
    except (ValueError, TypeError) as exc:
        raise InvalidCursorError() from exc
    if parsed_time.tzinfo is None:
        raise InvalidCursorError()
    return parsed_time.astimezone(UTC), parsed_id
