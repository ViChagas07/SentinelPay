import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from paysentineliq.application.errors import (
    AnalysisNotFoundError,
    InvalidCursorError,
)
from paysentineliq.application.ports.analysis_read_repository import AnalysisSummary
from paysentineliq.application.queries.analyses import (
    GetAnalysisHandler,
    ListAnalysesHandler,
)
from paysentineliq.application.queries.analysis_cursor import decode_cursor, encode_cursor
from paysentineliq.domain.analysis import AnalysisDocumentType, AnalysisStatus
from paysentineliq.domain.scoring import RiskBand

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_OWNER = uuid4()


def _summary(
    *,
    analysis_id: UUID | None = None,
    owner_id: UUID = _OWNER,
    status: AnalysisStatus = AnalysisStatus.COMPLETED,
    created_at: datetime = _NOW,
    report_s3_key: str | None = "reports/a.json",
    score: int | None = 80,
    error_code: str | None = None,
) -> AnalysisSummary:
    return AnalysisSummary(
        id=analysis_id or uuid4(),
        owner_id=owner_id,
        document_id=uuid4(),
        document_type=AnalysisDocumentType.BOLETO,
        status=status,
        score=score,
        band=RiskBand.HIGH if score is not None else None,
        error_code=error_code,
        report_s3_key=report_s3_key,
        created_at=created_at,
        updated_at=created_at,
    )


class FakeReadRepository:
    def __init__(self, summaries: tuple[AnalysisSummary, ...]) -> None:
        self._summaries = summaries
        self.list_calls = 0

    async def get_for_owner(
        self,
        analysis_id: UUID,
        owner_id: UUID,
    ) -> AnalysisSummary | None:
        return next(
            (
                summary
                for summary in self._summaries
                if summary.id == analysis_id and summary.owner_id == owner_id
            ),
            None,
        )

    async def list_for_owner(
        self,
        owner_id: UUID,
        *,
        limit: int,
        before: tuple[datetime, UUID] | None = None,
    ) -> tuple[AnalysisSummary, ...]:
        self.list_calls += 1
        filtered = [
            summary
            for summary in self._summaries
            if summary.owner_id == owner_id
            and (before is None or (summary.created_at, summary.id) < before)
        ]
        filtered.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return tuple(filtered[:limit])


class FakeStorage:
    def __init__(self, payload: bytes | None) -> None:
        self._payload = payload

    async def put(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None

    def get_stream(self, key: str) -> Any:
        async def stream() -> Any:
            if self._payload is not None:
                yield self._payload

        return stream()

    async def presigned_get_url(self, key: str, *, expires_in: int) -> str:
        return "https://example.test/report"


def _report() -> bytes:
    return json.dumps(
        {
            "score": 80,
            "band": "high",
            "base_score": 78,
            "llm_adjustment": 2,
            "evidence": [
                {
                    "rule_id": "dv_invalid",
                    "severity": "critical",
                    "weight": 70,
                    "message_key": "boleto.dv_invalid",
                    "source": "febraban-v1",
                },
            ],
            "justification": "DV invalido.",
            "inconsistencies": ["Sugestao."],
            "degradation_flags": ["llm_unavailable"],
            "fields": {"payer": "NAO DEVE SAIR"},
        },
    ).encode()


async def test_detail_returns_score_evidence_and_justification_without_fields() -> None:
    summary = _summary()
    handler = GetAnalysisHandler(FakeReadRepository((summary,)), FakeStorage(_report()))

    result = await handler.handle(summary.id, _OWNER)

    assert result.status is AnalysisStatus.COMPLETED
    assert result.result_available is True
    assert result.result is not None
    assert result.result.score == 80
    assert result.result.band is RiskBand.HIGH
    assert result.result.evidence[0].rule_id == "dv_invalid"
    assert result.result.justification == "DV invalido."
    assert not hasattr(result.result, "fields")


async def test_detail_of_other_owner_is_not_found() -> None:
    summary = _summary()
    handler = GetAnalysisHandler(FakeReadRepository((summary,)), FakeStorage(_report()))

    with pytest.raises(AnalysisNotFoundError):
        await handler.handle(summary.id, uuid4())


async def test_failed_analysis_has_safe_error_and_no_result() -> None:
    summary = _summary(
        status=AnalysisStatus.FAILED,
        report_s3_key=None,
        score=None,
        error_code="ocr_failed",
    )
    handler = GetAnalysisHandler(FakeReadRepository((summary,)), FakeStorage(None))

    result = await handler.handle(summary.id, _OWNER)

    assert result.status is AnalysisStatus.FAILED
    assert result.result is None
    assert result.error_code == "ocr_failed"


async def test_missing_report_is_unavailable_instead_of_leaking() -> None:
    summary = _summary()
    handler = GetAnalysisHandler(FakeReadRepository((summary,)), FakeStorage(b"not-json"))

    result = await handler.handle(summary.id, _OWNER)

    assert result.result_available is False
    assert result.result is None


async def test_list_uses_cursor_and_returns_next_page() -> None:
    summaries = tuple(
        _summary(
            analysis_id=uuid4(),
            created_at=_NOW - timedelta(minutes=index),
        )
        for index in range(3)
    )
    repository = FakeReadRepository(summaries)
    handler = ListAnalysesHandler(repository)

    first = await handler.handle(_OWNER, limit=2)
    assert len(first.items) == 2
    assert first.next_cursor is not None
    second = await handler.handle(_OWNER, limit=2, cursor=first.next_cursor)

    assert len(second.items) == 1
    assert second.next_cursor is None
    assert repository.list_calls == 2


async def test_list_of_other_owner_is_empty() -> None:
    handler = ListAnalysesHandler(FakeReadRepository((_summary(),)))

    result = await handler.handle(uuid4(), limit=20)

    assert result.items == ()


def test_cursor_roundtrip() -> None:
    analysis_id = uuid4()

    cursor = encode_cursor(_NOW, analysis_id)

    decoded_time, decoded_id = decode_cursor(cursor)
    assert decoded_time == _NOW
    assert decoded_id == analysis_id


@pytest.mark.parametrize("cursor", ["", "not-base64", "eyJpZCI6ICJ4In0"])
def test_invalid_cursor_is_rejected(cursor: str) -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor(cursor)
