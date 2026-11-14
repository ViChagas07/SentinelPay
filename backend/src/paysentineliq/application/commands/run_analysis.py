from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from paysentineliq.application.errors import (
    AnalysisTimeoutError,
    DocumentNotFoundError,
    LlmUnavailableError,
    RagUnavailableError,
    UnsupportedDocumentError,
)
from paysentineliq.application.ports.analysis import (
    AnalysisDocumentPort,
    AnalysisEventPort,
    AnalysisOrchestratorPort,
    AnalysisRepositoryPort,
    document_type_for,
)
from paysentineliq.domain.analysis import (
    AnalysisEvent,
    AnalysisEventType,
    AnalysisRecord,
    AnalysisReport,
    AnalysisStatus,
)


class RunAnalysisUseCase:
    def __init__(
        self,
        source: AnalysisDocumentPort,
        orchestrator: AnalysisOrchestratorPort,
        analyses: AnalysisRepositoryPort,
        events: AnalysisEventPort,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._source = source
        self._orchestrator = orchestrator
        self._analyses = analyses
        self._events = events
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self,
        document_id: UUID,
        *,
        locale: str = "pt",
    ) -> AnalysisReport:
        document = await self._source.get(document_id)
        if document is None:
            raise DocumentNotFoundError()
        document_type = document_type_for(document.kind)
        if document_type is None:
            raise UnsupportedDocumentError()
        analysis_id = uuid4()
        now = self._clock()
        await self._analyses.create(
            AnalysisRecord(
                id=analysis_id,
                owner_id=document.owner_id,
                document_id=document.id,
                document_type=document_type,
                status=AnalysisStatus.QUEUED,
                score=None,
                band=None,
                rule_set_version=None,
                model_versions={},
                degradation_flags=(),
                state={},
                report_s3_key=None,
                error_code=None,
                created_at=now,
                updated_at=now,
            ),
        )
        await self._events.append(
            AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.QUEUED,
                payload={"document_id": str(document.id)},
            ),
        )
        try:
            data = await self._source.read(document)
            return await self._orchestrator.run(
                analysis_id=analysis_id,
                document=document,
                data=data,
                locale=locale,
            )
        except Exception as error:
            error_code = self._error_code(error)
            await self._analyses.fail(
                analysis_id,
                error_code=error_code,
                state={"node": "run"},
            )
            await self._events.append(
                AnalysisEvent(
                    analysis_id=analysis_id,
                    event_type=AnalysisEventType.FAILED,
                    payload={"error": error_code},
                ),
            )
            raise

    @staticmethod
    def _error_code(error: Exception) -> str:
        if isinstance(error, AnalysisTimeoutError):
            return "analysis_timeout"
        if isinstance(error, UnsupportedDocumentError):
            return "unsupported_document"
        if isinstance(error, LlmUnavailableError):
            return "llm_unavailable"
        if isinstance(error, RagUnavailableError):
            return "rag_unavailable"
        if isinstance(error, DocumentNotFoundError):
            return "document_not_found"
        return "analysis_failed"
