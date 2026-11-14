from datetime import date

import pytest

from paysentineliq.domain.knowledge import Provenance
from paysentineliq.domain.knowledge_metadata import (
    compute_document_hash,
    extract_metadata,
)

pytestmark = pytest.mark.unit


def test_official_source_is_classified_and_dates_are_parsed() -> None:
    text = "\n".join(
        [
            "Manual FEBRABAN",
            "Fonte: https://www.bcb.gov.br/estabilidadefinanceira/norma",
            "Versao: 1.2",
            "Vigencia: 01/01/2024 a 31/12/2024",
            "Conteudo.",
        ],
    )

    metadata = extract_metadata(
        path="knowledge/febraban/manual.pdf",
        category="febraban",
        text=text,
    )

    assert metadata.title == "Manual FEBRABAN"
    assert metadata.source == "https://www.bcb.gov.br/estabilidadefinanceira/norma"
    assert metadata.provenance is Provenance.OFFICIAL
    assert metadata.version == "1.2"
    assert metadata.valid_from == date(2024, 1, 1)
    assert metadata.valid_until == date(2024, 12, 31)


def test_non_official_source_is_compiled() -> None:
    metadata = extract_metadata(
        path="knowledge/faq/x.pdf",
        category="faq",
        text="Perguntas\nFonte: blog.example.com/post\nConteudo",
    )

    assert metadata.provenance is Provenance.COMPILED


def test_missing_source_is_unknown() -> None:
    metadata = extract_metadata(
        path="knowledge/glossary/glossary.pdf",
        category="glossary",
        text="Glossario\nSem fonte declarada.",
    )

    assert metadata.source == "unknown"
    assert metadata.provenance is Provenance.UNKNOWN
    assert metadata.version is None
    assert metadata.valid_from is None
    assert metadata.valid_until is None


def test_document_hash_changes_with_text_or_metadata() -> None:
    base = extract_metadata(
        path="knowledge/faq/a.pdf",
        category="faq",
        text="Titulo\nConteudo A",
    )
    other_text = extract_metadata(
        path="knowledge/faq/a.pdf",
        category="faq",
        text="Titulo\nConteudo B",
    )
    other_meta = extract_metadata(
        path="knowledge/faq/a.pdf",
        category="faq",
        text="Outro titulo\nConteudo A",
    )

    first = compute_document_hash(
        category="faq",
        path="knowledge/faq/a.pdf",
        metadata=base,
        page_texts=("Titulo\nConteudo A",),
    )
    second = compute_document_hash(
        category="faq",
        path="knowledge/faq/a.pdf",
        metadata=base,
        page_texts=("Titulo\nConteudo A",),
    )

    assert first == second
    assert first != compute_document_hash(
        category="faq",
        path="knowledge/faq/a.pdf",
        metadata=other_text,
        page_texts=("Titulo\nConteudo B",),
    )
    assert first != compute_document_hash(
        category="faq",
        path="knowledge/faq/a.pdf",
        metadata=other_meta,
        page_texts=("Outro titulo\nConteudo A",),
    )
