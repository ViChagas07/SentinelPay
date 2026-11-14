import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from paysentineliq.application.commands.process_analysis import (
    ProcessedAnalysis,
    is_retryable_analysis_error,
)
from paysentineliq.domain.analysis import AnalysisEvent, AnalysisEventType
from paysentineliq.infrastructure.config import get_settings
from paysentineliq.infrastructure.db.repositories.analyses import (
    SqlAlchemyAnalysisRepository,
)
from paysentineliq.infrastructure.messaging.async_bridge import run_async
from paysentineliq.infrastructure.messaging.celery_app import (
    ANALYSIS_TASK,
    NOTIFICATION_TASK,
    SWEEP_TASK,
    celery_app,
)
from paysentineliq.infrastructure.messaging.dispatcher import CeleryTaskDispatcher

_logger = logging.getLogger("paysentineliq")

_DEFAULT_MAX_RETRIES = 3


async def _execute_analysis(
    analysis_id: UUID,
    *,
    task_id: str,
    attempt: int,
    final_attempt: bool,
    locale: str,
) -> ProcessedAnalysis:
    from paysentineliq.infrastructure.composition.analysis_worker import (
        build_worker_runtime,
    )

    async with build_worker_runtime(get_settings()) as handler:
        return await handler.execute(
            analysis_id,
            task_id=task_id,
            attempt=attempt,
            final_attempt=final_attempt,
            locale=locale,
        )


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=ANALYSIS_TASK,
    max_retries=_DEFAULT_MAX_RETRIES,
)
def run_analysis_task(self: Any, analysis_id: str, locale: str = "pt") -> dict[str, str]:
    try:
        parsed_id = UUID(str(analysis_id))
    except (TypeError, ValueError):
        _logger.error("analysis_task_invalid_id")
        return {"status": "discarded"}
    retries = int(self.request.retries or 0)
    max_retries = int(self.max_retries if self.max_retries is not None else _DEFAULT_MAX_RETRIES)
    task_id = str(self.request.id or parsed_id)
    try:
        result = run_async(
            lambda: _execute_analysis(
                parsed_id,
                task_id=task_id,
                attempt=retries + 1,
                final_attempt=retries >= max_retries,
                locale=locale,
            ),
        )
    except Exception as error:
        if is_retryable_analysis_error(error) and retries < max_retries:
            raise self.retry(exc=error) from error
        raise
    dispatcher = CeleryTaskDispatcher(celery_app)
    for notification_id in result.notification_ids:
        try:
            dispatcher.dispatch_notification(notification_id)
        except Exception:
            _logger.error("notification_dispatch_failed")
    return {"status": result.status}


@celery_app.task(name=NOTIFICATION_TASK)  # type: ignore[untyped-decorator]
def dispatch_notification(notification_id: str) -> str:
    try:
        UUID(str(notification_id))
    except (TypeError, ValueError):
        _logger.error("notification_task_invalid_id")
        return "discarded"
    _logger.info("notification_pending_delivery")
    return "pending"


@celery_app.task(name=SWEEP_TASK)  # type: ignore[untyped-decorator]
def sweep_stale_analyses() -> int:
    return run_async(_sweep_stale_analyses)


async def _sweep_stale_analyses() -> int:
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        repository = SqlAlchemyAnalysisRepository(session_factory)
        cutoff = datetime.now(UTC) - timedelta(seconds=settings.analysis_lease_seconds)
        stale = await repository.list_stale_processing(cutoff)
        dispatcher = CeleryTaskDispatcher(celery_app)
        requeued = 0
        for record in stale:
            if await repository.requeue_for_retry(
                record.id,
                error_code="analysis_stale",
                state={"node": "sweep", "error": "analysis_stale"},
                event=AnalysisEvent(
                    analysis_id=record.id,
                    event_type=AnalysisEventType.RETRY_SCHEDULED,
                    payload={"error_code": "analysis_stale"},
                ),
            ):
                requeued += 1
                try:
                    dispatcher.dispatch_analysis(record.id)
                except Exception:
                    _logger.error("stale_analysis_dispatch_failed")
        return requeued
    finally:
        await engine.dispose()
