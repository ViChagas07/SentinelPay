from dataclasses import dataclass
from typing import Protocol

from paysentineliq.domain.knowledge import KnowledgeDocument


@dataclass(frozen=True, slots=True)
class SourceScan:
    documents: tuple[KnowledgeDocument, ...]
    skipped_directories: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()


class KnowledgeSourcePort(Protocol):
    def scan(self) -> SourceScan: ...
