import hashlib
import itertools
from typing import Literal

import pytest

from paysentineliq.domain.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    Provenance,
    SourcePage,
)
from paysentineliq.domain.knowledge_chunking import (
    ChunkingConfig,
    chunk_markdown,
    chunk_pages,
)

pytestmark = pytest.mark.unit


def _document(
    pages: tuple[SourcePage, ...],
    *,
    fmt: Literal["pdf", "markdown"] = "pdf",
) -> KnowledgeDocument:
    return KnowledgeDocument(
        key="febraban/manual.pdf",
        category="febraban",
        path="knowledge/febraban/manual.pdf",
        title="Manual",
        source="unknown",
        provenance=Provenance.UNKNOWN,
        version=None,
        valid_from=None,
        valid_until=None,
        content_hash="a" * 64,
        pages=pages,
        format=fmt,
    )


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_short_pdf_pages_become_one_chunk_each() -> None:
    document = _document(
        (
            SourcePage(number=1, text="Pagina um\nConteudo A"),
            SourcePage(number=2, text="Pagina dois\nConteudo B"),
        ),
    )

    chunks = chunk_pages(document, ChunkingConfig())

    assert len(chunks) == 2
    assert [chunk.section for chunk in chunks] == ["page 1", "page 2"]
    assert chunks[0].content_hash == _hash(chunks[0].content)
    assert chunks[1].position > chunks[0].position
    assert all(isinstance(chunk, KnowledgeChunk) for chunk in chunks)


def test_large_page_splits_with_overlap_and_preserves_lines() -> None:
    paragraphs = "\n\n".join(f"Paragrafo {index} " + ("texto " * 40) for index in range(12))
    document = _document((SourcePage(number=1, text=paragraphs),))

    chunks = chunk_pages(
        document,
        ChunkingConfig(target_chars=500, overlap_chars=80),
    )

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 700 for chunk in chunks)
    for first, second in itertools.pairwise(chunks):
        assert first.content[-40:] in second.content
    joined = "\n".join(chunk.content for chunk in chunks)
    assert "Paragrafo 0" in joined
    assert "Paragrafo 11" in joined


def test_table_block_is_not_split() -> None:
    table = "\n".join(f"| Campo {index} | Valor {index} |" for index in range(30))
    text = "Introducao curta.\n\n" + table + "\n\nFim."
    document = _document((SourcePage(number=1, text=text),))

    chunks = chunk_pages(
        document,
        ChunkingConfig(target_chars=200, overlap_chars=20),
    )

    table_chunks = [chunk for chunk in chunks if "| Campo 0 |" in chunk.content]
    assert len(table_chunks) == 1
    assert all(
        f"| Campo {index} | Valor {index} |" in table_chunks[0].content for index in range(30)
    )


def test_markdown_sections_use_heading_paths() -> None:
    text = "\n".join(
        [
            "# Manual",
            "Introducao.",
            "## Layout",
            "Detalhe do layout.",
            "### Campos",
            "Campo A.",
            "## Outro",
            "Fim.",
        ],
    )

    chunks = chunk_markdown(
        text,
        document_key="febraban/manual.md",
        config=ChunkingConfig(target_chars=200, overlap_chars=20),
    )

    sections = {chunk.section for chunk in chunks}
    assert "Manual" in sections
    assert "Manual > Layout" in sections
    assert "Manual > Layout > Campos" in sections
    assert "Manual > Outro" in sections


def test_chunking_is_deterministic() -> None:
    document = _document((SourcePage(number=1, text="A\n\nB\n\nC"),))

    first = chunk_pages(document, ChunkingConfig())
    second = chunk_pages(document, ChunkingConfig())

    assert first == second


def test_chunking_config_validates_overlap() -> None:
    with pytest.raises(ValueError):
        ChunkingConfig(target_chars=100, overlap_chars=100)
    with pytest.raises(ValueError):
        ChunkingConfig(target_chars=0)
