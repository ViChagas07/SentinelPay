from uuid import uuid4

import pytest

from paysentineliq.application.security.storage_keys import (
    build_analysis_report_key,
    build_original_key,
    build_report_key,
    sanitize_filename,
)
from paysentineliq.domain.document import DocumentKind

pytestmark = pytest.mark.unit


def test_original_key_is_owner_scoped_and_system_generated() -> None:
    owner_id = uuid4()
    analysis_id = uuid4()

    key = build_original_key(
        owner_id=owner_id,
        kind=DocumentKind.BANK_SLIP,
        analysis_id=analysis_id,
        extension="PDF",
    )

    assert key == (f"users/{owner_id}/bank_slip/{analysis_id}/original.pdf")


def test_report_key_is_owner_scoped() -> None:
    owner_id = uuid4()
    analysis_id = uuid4()

    key = build_report_key(
        owner_id=owner_id,
        kind=DocumentKind.PAYSLIP,
        analysis_id=analysis_id,
    )

    assert key == f"users/{owner_id}/payslip/{analysis_id}/report.json"


def test_unknown_extension_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_original_key(
            owner_id=uuid4(),
            kind=DocumentKind.RECEIPT,
            analysis_id=uuid4(),
            extension="exe",
        )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd", "passwd"),
        ("..\\..\\evil.pdf", "evil.pdf"),
        ("<script>.pdf", "script.pdf"),
        ("..", "upload"),
        ("   ", "upload"),
        (None, "upload"),
    ],
)
def test_filename_is_sanitized(raw: str | None, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_long_filename_is_truncated() -> None:
    assert len(sanitize_filename("a" * 500)) == 200


def test_analysis_report_key_is_owner_scoped() -> None:
    owner_id = uuid4()
    analysis_id = uuid4()

    assert (
        build_analysis_report_key(
            owner_id=owner_id,
            analysis_id=analysis_id,
        )
        == f"users/{owner_id}/analyses/{analysis_id}/report.json"
    )
