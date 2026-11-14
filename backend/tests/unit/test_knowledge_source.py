from pathlib import Path

import pymupdf
import pytest

from paysentineliq.domain.knowledge import Provenance
from paysentineliq.infrastructure.rag.source import KnowledgeFileSource

pytestmark = pytest.mark.unit


def _write_pdf(path: Path, text: str) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def test_scan_reads_pdf_and_markdown_and_skips_weird_directory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "knowledge"
    (root / "febraban").mkdir(parents=True)
    (root / "faq").mkdir()
    weird = root / "{febraban,bacen}"
    weird.mkdir()

    _write_pdf(
        root / "febraban" / "manual.pdf",
        "Manual FEBRABAN\nFonte: https://www.bcb.gov.br/norma\nConteudo",
    )
    (root / "faq" / "faq.md").write_text(
        "# FAQ\nFonte: blog.example.com\nConteudo",
        encoding="utf-8",
    )
    _write_pdf(weird / "ignored.pdf", "Ignorado")

    scan = KnowledgeFileSource(root).scan()

    assert len(scan.documents) == 2
    assert all(len(document.content_hash) == 64 for document in scan.documents)
    assert "{febraban,bacen}" in scan.skipped_directories

    by_key = {document.key: document for document in scan.documents}
    pdf = by_key["febraban/manual.pdf"]
    markdown = by_key["faq/faq.md"]
    assert pdf.format == "pdf"
    assert pdf.provenance is Provenance.OFFICIAL
    assert pdf.path == "knowledge/febraban/manual.pdf"
    assert markdown.format == "markdown"
    assert markdown.provenance is Provenance.COMPILED
    assert markdown.pages[0].text.startswith("# FAQ")


def test_scan_ignores_unsupported_files(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    (root / "faq").mkdir(parents=True)
    (root / "faq" / "notes.txt").write_text("ignored", encoding="utf-8")

    scan = KnowledgeFileSource(root).scan()

    assert scan.documents == ()
    assert scan.skipped_directories == ()
