from pathlib import Path
from typing import Literal

import pymupdf

from paysentineliq.application.ports.knowledge_source import SourceScan
from paysentineliq.domain.knowledge import KnowledgeDocument, SourcePage
from paysentineliq.domain.knowledge_metadata import (
    compute_document_hash,
    extract_metadata,
)
from paysentineliq.infrastructure.rag.text_cleanup import repair_text

_ALLOWED_SUFFIXES = {".pdf", ".md"}


class KnowledgeFileSource:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def scan(self) -> SourceScan:
        documents: list[KnowledgeDocument] = []
        skipped_directories: list[str] = []
        failures: list[str] = []
        if not self._root.is_dir():
            return SourceScan(
                documents=(),
                failures=(f"{self._root.name}: knowledge root not found",),
            )

        for category_dir in sorted(self._root.iterdir(), key=lambda path: path.name):
            if not category_dir.is_dir():
                continue
            if any(char in category_dir.name for char in "{},"):
                skipped_directories.append(category_dir.name)
                continue
            if category_dir.name.startswith("."):
                continue
            for file in sorted(category_dir.iterdir(), key=lambda path: path.name):
                if not file.is_file() or file.suffix.lower() not in _ALLOWED_SUFFIXES:
                    continue
                if not file.resolve().is_relative_to(self._root):
                    failures.append(f"{category_dir.name}/{file.name}: outside root")
                    continue
                try:
                    pages, document_format = self._read(file)
                except Exception:
                    failures.append(f"{category_dir.name}/{file.name}: unreadable")
                    continue
                if not pages or not any(page.text.strip() for page in pages):
                    failures.append(f"{category_dir.name}/{file.name}: no text")
                    continue
                full_text = "\n".join(page.text for page in pages)
                path = f"knowledge/{category_dir.name}/{file.name}"
                metadata = extract_metadata(
                    path=path,
                    category=category_dir.name,
                    text=full_text,
                )
                documents.append(
                    KnowledgeDocument(
                        key=f"{category_dir.name}/{file.name}",
                        category=category_dir.name,
                        path=path,
                        title=metadata.title,
                        source=metadata.source,
                        provenance=metadata.provenance,
                        version=metadata.version,
                        valid_from=metadata.valid_from,
                        valid_until=metadata.valid_until,
                        content_hash=compute_document_hash(
                            category=category_dir.name,
                            path=path,
                            metadata=metadata,
                            page_texts=tuple(page.text for page in pages),
                        ),
                        pages=pages,
                        format=document_format,
                    ),
                )
        return SourceScan(
            documents=tuple(documents),
            skipped_directories=tuple(skipped_directories),
            failures=tuple(failures),
        )

    def _read(
        self,
        path: Path,
    ) -> tuple[tuple[SourcePage, ...], Literal["pdf", "markdown"]]:
        if path.suffix.lower() == ".md":
            text = repair_text(path.read_text(encoding="utf-8", errors="replace"))
            return (SourcePage(number=1, text=text),), "markdown"
        document = pymupdf.open(path)
        try:
            pages = tuple(
                SourcePage(number=index, text=repair_text(page.get_text()))
                for index, page in enumerate(document, start=1)
            )
        finally:
            document.close()
        return pages, "pdf"
