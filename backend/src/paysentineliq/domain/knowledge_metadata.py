import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from paysentineliq.domain.knowledge import Provenance

_SOURCE_RE = re.compile(r"(?im)^\s*(?:fonte|source)\s*:\s*(.+)$")
_VERSION_RE = re.compile(r"(?im)^\s*(?:versao|versão|version)\s*:\s*(.+)$")
_VALIDITY_RE = re.compile(
    r"(?im)^\s*(?:vigencia|vigência|validade|valido|válido)\s*:\s*(.+)$",
)
_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})\b")
_OFFICIAL_DOMAINS = (
    "gov.br",
    "bcb.gov.br",
    "febraban.org.br",
    "planalto.gov.br",
    "inss.gov.br",
    "receita.fazenda.gov.br",
)


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    title: str
    source: str
    provenance: Provenance
    version: str | None
    valid_from: date | None
    valid_until: date | None


def _parse_date(value: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return (
                date.fromisoformat(value)
                if fmt == "%Y-%m-%d"
                else date(
                    int(value[6:10]),
                    int(value[3:5]),
                    int(value[0:2]),
                )
            )
        except ValueError:
            continue
    return None


def _title(path: str, text: str) -> str:
    for line in text.splitlines():
        candidate = line.strip()
        if len(candidate) >= 3 and not candidate.isdigit():
            return candidate[:160]
    return Path(path).stem[:160]


def _source(text: str) -> str:
    match = _SOURCE_RE.search(text)
    if match is None:
        return "unknown"
    source = " ".join(match.group(1).split()).strip(" .;")
    if not source or source.lower() in ("unknown", "n/a", "na"):
        return "unknown"
    return source


def _provenance(source: str) -> Provenance:
    if source == "unknown":
        return Provenance.UNKNOWN
    lowered = source.lower()
    if any(domain in lowered for domain in _OFFICIAL_DOMAINS):
        return Provenance.OFFICIAL
    return Provenance.COMPILED


def _version(text: str) -> str | None:
    match = _VERSION_RE.search(text)
    if match is None:
        return None
    version = " ".join(match.group(1).split()).strip(" .;")
    return version[:80] or None


def _validity(text: str) -> tuple[date | None, date | None]:
    match = _VALIDITY_RE.search(text)
    if match is None:
        return None, None
    value = match.group(1).strip()
    parsed = [parsed for raw in _DATE_RE.findall(value) if (parsed := _parse_date(raw))]
    if not parsed:
        return None, None
    lowered = value.lower()
    if len(parsed) >= 2:
        start, end = parsed[0], parsed[1]
        return (start, end) if start <= end else (end, start)
    if any(token in lowered for token in ("ate", "até", "fim", "final")):
        return None, parsed[0]
    return parsed[0], None


def extract_metadata(
    *,
    path: str,
    category: str,
    text: str,
) -> DocumentMetadata:
    source = _source(text)
    valid_from, valid_until = _validity(text)
    return DocumentMetadata(
        title=_title(path, text),
        source=source,
        provenance=_provenance(source),
        version=_version(text),
        valid_from=valid_from,
        valid_until=valid_until,
    )


def compute_document_hash(
    *,
    category: str,
    path: str,
    metadata: DocumentMetadata,
    page_texts: tuple[str, ...],
) -> str:
    payload = {
        "category": category,
        "path": path,
        "title": metadata.title,
        "source": metadata.source,
        "provenance": metadata.provenance.value,
        "version": metadata.version,
        "valid_from": metadata.valid_from.isoformat() if metadata.valid_from else None,
        "valid_until": metadata.valid_until.isoformat() if metadata.valid_until else None,
        "pages": list(page_texts),
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
