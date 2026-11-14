from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from paysentineliq.application.commands.run_analysis import RunAnalysisUseCase
from paysentineliq.application.errors import (
    AnalysisTimeoutError,
    DocumentNotFoundError,
    UnsupportedDocumentError,
)
from paysentineliq.application.ports.analysis import AnalysisDocument
from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisEvent,
    AnalysisEventType,
    AnalysisRecord,
    AnalysisReport,
    AnalysisStatus,
    DegradationFlag,
)
from paysentineliq.domain.document import DocumentKind
from paysentineliq.domain.scoring import RiskBand

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeSource:
    def __init__(
        self,
        document: AnalysisDocument | None,
        *,
        data: bytes = b"data",
        read_error: Exception | None = None,
    ) -> None:
        self._document = document
        self._data = data
        self._read_error = read_error
        self.read_calls = 0

    async def get(self, document_id: UUID) -> AnalysisDocument | None:
        if self._document is not None and self._document.id != document_id:
            return None
        return self._document

    async def read(self, document: AnalysisDocument) -> bytes:
        self.read_calls += 1
        if self._read_error is not None:
            raise self._read_error
        return self._data


class FakeOrchestrator:
    def __init__(
        self,
        *,
        error: Exception | None = None,
    ) -> None:
        self._error = error
        self.calls: list[dict[str, object]] = []

    async def run(
        self,
        *,
        analysis_id: UUID,
        document: AnalysisDocument,
        data: bytes,
        locale: str = "pt",
    ) -> AnalysisReport:
        self.calls.append(
            {
                "analysis_id": analysis_id,
                "document": document,
                "data": data,
                "locale": locale,
            },
        )
        if self._error is not None:
            raise self._error
        return AnalysisReport(
            analysis_id=analysis_id,
            document_id=document.id,
            document_type=AnalysisDocumentType.BOLETO,
            score=10,
            band=RiskBand.LOW,
            base_score=10,
            llm_adjustment=0,
            fields={},
            evidence=(),
            justification="ok",
            inconsistencies=(),
            rule_set_version="test",
            model_versions={},
            degradation_flags=(),
            report_s3_key=f"users/{document.owner_id}/analyses/{analysis_id}/report.json",
            created_at=_NOW,
        )


class FakeAnalysisRepository:
    def __init__(self) -> None:
        self.created: AnalysisRecord | None = None
        self.failed: dict[str, object] | None = None

    async def create(self, record: AnalysisRecord) -> None:
        self.created = record

    async def update_state(
        self,
        analysis_id: UUID,
        *,
        status: AnalysisStatus,
        state: Mapping[str, object],
        degradation_flags: tuple[DegradationFlag, ...],
    ) -> None:
        return None

    async def complete(
        self,
        analysis_id: UUID,
        *,
        score: int,
        band: RiskBand,
        rule_set_version: str,
        model_versions: Mapping[str, str],
        degradation_flags: tuple[DegradationFlag, ...],
        state: Mapping[str, object],
        report_s3_key: str,
    ) -> None:
        return None

    async def fail(
        self,
        analysis_id: UUID,
        *,
        error_code: str,
        state: Mapping[str, object],
    ) -> None:
        self.failed = {"analysis_id": analysis_id, "error_code": error_code}


class FakeEventRepository:
    def __init__(self) -> None:
        self.events: list[AnalysisEvent] = []

    async def append(self, event: AnalysisEvent) -> None:
        self.events.append(event)


def _document(kind: DocumentKind = DocumentKind.BANK_SLIP) -> AnalysisDocument:
    return AnalysisDocument(
        id=uuid4(),
        owner_id=uuid4(),
        kind=kind,
        s3_key="users/owner/bank_slip/analysis/original.pdf",
        content_type="application/pdf",
        size=4,
    )


def _use_case(
    source: FakeSource,
    orchestrator: FakeOrchestrator,
) -> tuple[RunAnalysisUseCase, FakeAnalysisRepository, FakeEventRepository]:
    analyses = FakeAnalysisRepository()
    events = FakeEventRepository()
    return (
        RunAnalysisUseCase(
            source,
            orchestrator,
            analyses,
            events,
            clock=lambda: _NOW,
        ),
        analyses,
        events,
    )


async def test_success_creates_analysis_and_returns_report() -> None:
    document = _document()
    source = FakeSource(document)
    orchestrator = FakeOrchestrator()
    use_case, analyses, events = _use_case(source, orchestrator)

    report = await use_case.execute(document.id, locale="es")

    assert report.score == 10
    assert analyses.created is not None
    assert analyses.created.status is AnalysisStatus.QUEUED
    assert analyses.created.owner_id == document.owner_id
    assert analyses.created.document_type is AnalysisDocumentType.BOLETO
    assert events.events[0].event_type is AnalysisEventType.QUEUED
    assert orchestrator.calls[0]["data"] == b"data"
    assert orchestrator.calls[0]["locale"] == "es"


async def test_missing_document_raises_without_creating_analysis() -> None:
    use_case, analyses, events = _use_case(FakeSource(None), FakeOrchestrator())

    with pytest.raises(DocumentNotFoundError):
        await use_case.execute(uuid4())

    assert analyses.created is None
    assert events.events == []


async def test_unsupported_document_raises_without_creating_analysis() -> None:
    document = _document(DocumentKind.RECEIPT)
    use_case, analyses, _ = _use_case(FakeSource(document), FakeOrchestrator())

    with pytest.raises(UnsupportedDocumentError):
        await use_case.execute(document.id)

    assert analyses.created is None


async def test_orchestrator_failure_marks_analysis_failed() -> None:
    document = _document()
    use_case, analyses, events = _use_case(
        FakeSource(document),
        FakeOrchestrator(error=RuntimeError("boom")),
    )

    with pytest.raises(RuntimeError):
        await use_case.execute(document.id)

    assert analyses.failed is not None
    assert analyses.failed["error_code"] == "analysis_failed"
    assert [event.event_type for event in events.events] == [
        AnalysisEventType.QUEUED,
        AnalysisEventType.FAILED,
    ]


async def test_read_failure_marks_analysis_failed() -> None:
    document = _document()
    use_case, analyses, events = _use_case(
        FakeSource(document, read_error=OSError("storage offline")),
        FakeOrchestrator(),
    )

    with pytest.raises(OSError):
        await use_case.execute(document.id)

    assert analyses.failed is not None
    assert analyses.failed["error_code"] == "analysis_failed"
    assert events.events[-1].event_type is AnalysisEventType.FAILED


async def test_timeout_has_specific_error_code() -> None:
    document = _document()
    use_case, analyses, _ = _use_case(
        FakeSource(document),
        FakeOrchestrator(error=AnalysisTimeoutError("ingest")),
    )

    with pytest.raises(AnalysisTimeoutError):
        await use_case.execute(document.id)

    assert analyses.failed is not None
    assert analyses.failed["error_code"] == "analysis_timeout"
