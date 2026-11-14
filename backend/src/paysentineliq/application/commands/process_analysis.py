import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from paysentineliq.application.errors import (
    AnalysisTimeoutError,
    DocumentNotFoundError,
    EmbeddingUnavailableError,
    InvalidDocumentError,
    LlmUnavailableError,
    OcrUnavailableError,
    RagUnavailableError,
    StorageUnavailableError,
    UnsupportedDocumentError,
    UploadTooLargeError,
)
from paysentineliq.application.ports.analysis import (
    AnalysisDocumentPort,
    AnalysisOrchestratorPort,
    AnalysisRepositoryPort,
)
from paysentineliq.application.ports.notification_repository import (
    NotificationRepositoryPort,
)
from paysentineliq.domain.analysis import AnalysisEvent, AnalysisEventType

_NON_RETRYABLE = (
    UnsupportedDocumentError,
    DocumentNotFoundError,
    InvalidDocumentError,
)


@dataclass(frozen=True, slots=True)
class ProcessedAnalysis:
    analysis_id: UUID
    status: str
    notification_ids: tuple[UUID, ...] = ()


class ProcessAnalysisHandler:
    def __init__(
        self,
        source: AnalysisDocumentPort,
        orchestrator: AnalysisOrchestratorPort,
        analyses: AnalysisRepositoryPort,
        notifications: NotificationRepositoryPort,
        *,
        lease_seconds: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self._source = source
        self._orchestrator = orchestrator
        self._analyses = analyses
        self._notifications = notifications
        self._lease_seconds = lease_seconds
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self,
        analysis_id: UUID,
        *,
        task_id: str,
        attempt: int,
        final_attempt: bool,
        locale: str = "pt",
    ) -> ProcessedAnalysis:
        if not task_id.strip():
            raise ValueError("task_id is required")
        claimed = await self._analyses.claim_for_processing(
            analysis_id,
            task_id=task_id,
            lease_seconds=self._lease_seconds,
            event=AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.PROCESSING,
                payload={"task_id": task_id, "attempt": str(attempt)},
            ),
        )
        if claimed is None:
            return ProcessedAnalysis(analysis_id=analysis_id, status="skipped")
        try:
            document = await self._source.get(claimed.document_id)
            if document is None:
                raise DocumentNotFoundError()
            data = await self._source.read(document)
            report = await self._orchestrator.run(
                analysis_id=analysis_id,
                document=document,
                data=data,
                locale=locale,
            )
        except Exception as error:
            error_code = analysis_error_code(error)
            if is_retryable_analysis_error(error) and not final_attempt:
                with contextlib.suppress(Exception):
                    await self._analyses.requeue_for_retry(
                        analysis_id,
                        error_code=error_code,
                        state={"node": "run", "attempt": str(attempt)},
                        event=AnalysisEvent(
                            analysis_id=analysis_id,
                            event_type=AnalysisEventType.RETRY_SCHEDULED,
                            payload={"error_code": error_code},
                        ),
                    )
            else:
                with contextlib.suppress(Exception):
                    await self._analyses.fail(
                        analysis_id,
                        error_code=error_code,
                        state={"node": "run", "error": error_code},
                        event=AnalysisEvent(
                            analysis_id=analysis_id,
                            event_type=AnalysisEventType.FAILED,
                            payload={"error_code": error_code},
                        ),
                    )
            raise
        notifications = await self._notifications.list_pending_for_analysis(analysis_id)
        return ProcessedAnalysis(
            analysis_id=analysis_id,
            status="degraded" if report.degradation_flags else "completed",
            notification_ids=tuple(item.id for item in notifications),
        )


def is_retryable_analysis_error(error: BaseException) -> bool:
    return not isinstance(error, _NON_RETRYABLE)


def analysis_error_code(error: BaseException) -> str:
    if isinstance(error, AnalysisTimeoutError):
        return "analysis_timeout"
    if isinstance(error, UnsupportedDocumentError):
        return "unsupported_document"
    if isinstance(error, DocumentNotFoundError):
        return "document_not_found"
    if isinstance(error, InvalidDocumentError):
        return "invalid_document"
    if isinstance(error, LlmUnavailableError):
        return "llm_unavailable"
    if isinstance(error, RagUnavailableError):
        return "rag_unavailable"
    if isinstance(error, StorageUnavailableError):
        return "storage_unavailable"
    if isinstance(error, OcrUnavailableError):
        return "ocr_unavailable"
    if isinstance(error, EmbeddingUnavailableError):
        return "embedding_unavailable"
    if isinstance(error, UploadTooLargeError):
        return "upload_too_large"
    return "analysis_failed"
