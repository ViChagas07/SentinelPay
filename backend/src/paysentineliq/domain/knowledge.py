from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Literal


class Provenance(StrEnum):
    OFFICIAL = "official"
    COMPILED = "compiled"
    UNKNOWN = "unknown"


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


@dataclass(frozen=True, slots=True)
class SourcePage:
    number: int
    text: str

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError("page number must be positive")


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    key: str
    category: str
    path: str
    title: str
    source: str
    provenance: Provenance
    version: str | None
    valid_from: date | None
    valid_until: date | None
    content_hash: str
    pages: tuple[SourcePage, ...]
    format: Literal["pdf", "markdown"] = "pdf"

    def __post_init__(self) -> None:
        if not self.key.strip() or not self.category.strip() or not self.path.strip():
            raise ValueError("document key, category and path are required")
        if not self.title.strip():
            raise ValueError("document title is required")
        if not self.source.strip():
            raise ValueError("document source is required")
        if not _is_sha256(self.content_hash):
            raise ValueError("content_hash must be a sha256 hex digest")
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_from > self.valid_until
        ):
            raise ValueError("valid_from must not be after valid_until")
        if self.format not in ("pdf", "markdown"):
            raise ValueError("format must be pdf or markdown")

    @property
    def authoritative(self) -> bool:
        return self.provenance is Provenance.OFFICIAL


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    document_key: str
    index: int
    section: str
    position: int
    content: str
    content_hash: str

    def __post_init__(self) -> None:
        if not self.document_key.strip():
            raise ValueError("document_key is required")
        if self.index < 0 or self.position < 0:
            raise ValueError("index and position must be non-negative")
        if not self.section.strip() or not self.content.strip():
            raise ValueError("section and content are required")
        if not _is_sha256(self.content_hash):
            raise ValueError("content_hash must be a sha256 hex digest")


@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    chunk: KnowledgeChunk
    embedding: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.embedding:
            raise ValueError("embedding must not be empty")


@dataclass(frozen=True, slots=True)
class KnowledgeFilter:
    categories: tuple[str, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    as_of: date | None = None


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    document_key: str
    path: str
    category: str
    title: str
    source: str
    provenance: Provenance
    version: str | None
    valid_from: date | None
    valid_until: date | None
    section: str
    content: str
    content_hash: str
    chunk_index: int
    score: float

    @property
    def authoritative(self) -> bool:
        return self.provenance is Provenance.OFFICIAL


@dataclass(frozen=True, slots=True)
class UpsertResult:
    document_key: str
    skipped: bool
    chunks_written: int
    chunks_deleted: int
