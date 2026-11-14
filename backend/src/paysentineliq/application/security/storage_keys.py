import re
from uuid import UUID

from paysentineliq.domain.document import DocumentKind

_ALLOWED_EXTENSIONS = frozenset({"pdf", "png", "jpg"})
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_NAME_LENGTH = 200


def build_original_key(
    *,
    owner_id: UUID,
    kind: DocumentKind,
    analysis_id: UUID,
    extension: str,
) -> str:
    normalized = extension.lower()
    if normalized not in _ALLOWED_EXTENSIONS:
        raise ValueError("unsupported extension")
    return f"users/{owner_id}/{kind.value}/{analysis_id}/original.{normalized}"


def build_report_key(
    *,
    owner_id: UUID,
    kind: DocumentKind,
    analysis_id: UUID,
) -> str:
    return f"users/{owner_id}/{kind.value}/{analysis_id}/report.json"


def sanitize_filename(name: str | None) -> str:
    if not name:
        return "upload"

    normalized = name.replace("\\", "/")
    base = normalized.rsplit("/", 1)[-1]
    base = _CONTROL_CHARS.sub("", base)
    base = "".join(character for character in base if character.isprintable())
    base = base.replace("<", "").replace(">", "").strip().strip(".")
    if not base:
        return "upload"
    return base[:_MAX_NAME_LENGTH]


def build_analysis_report_key(*, owner_id: UUID, analysis_id: UUID) -> str:
    return f"users/{owner_id}/analyses/{analysis_id}/report.json"
