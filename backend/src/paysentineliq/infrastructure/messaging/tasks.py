import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from paysentineliq.application.commands.process_analysis import (
    ProcessedAnalysis,
    is_retryable_analysis_error,
)
from paysentineliq.application.notifications.delivery import DeliveryOutcome
from paysentineliq.application.security.storage_keys import build_analysis_report_key
from paysentineliq.domain.analysis import AnalysisEvent, AnalysisEventType
from paysentineliq.infrastructure.config import get_settings
from paysentineliq.infrastructure.db.repositories.analyses import (
    SqlAlchemyAnalysisRepository,
)
from paysentineliq.infrastructure.db.repositories.payables import (
    SqlAlchemyPayableReminderRepository,
)
from paysentineliq.infrastructure.messaging.async_bridge import run_async
from paysentineliq.infrastructure.messaging.celery_app import (
    ANALYSIS_TASK,
    NOTIFICATION_TASK,
    PAYABLES_OVERDUE_TASK,
    PAYABLES_REMINDER_TASK,
    SWEEP_TASK,
    celery_app,
)
from paysentineliq.infrastructure.messaging.dispatcher import CeleryTaskDispatcher
from paysentineliq.infrastructure.observability.metrics import get_platform_metrics
from paysentineliq.infrastructure.storage.s3 import S3StorageAdapter

_logger = logging.getLogger("paysentineliq")
_CANCEL_FINALIZE_SECONDS = 120

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


async def _execute_notification(
    notification_id: UUID,
    *,
    final_attempt: bool,
) -> DeliveryOutcome:
    from paysentineliq.infrastructure.composition.notification_worker import (
        build_notification_runtime,
    )

    async with build_notification_runtime(get_settings()) as handler:
        return await handler.execute(notification_id, final_attempt=final_attempt)


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=NOTIFICATION_TASK,
    max_retries=get_settings().notifications_delivery_max_retries,
)
def dispatch_notification(self: Any, notification_id: str) -> dict[str, str]:
    try:
        parsed_id = UUID(str(notification_id))
    except (TypeError, ValueError):
        _logger.error("notification_task_invalid_id")
        return {"status": "discarded"}
    retries = int(self.request.retries or 0)
    max_retries = int(
        self.max_retries
        if self.max_retries is not None
        else get_settings().notifications_delivery_max_retries
    )
    outcome = run_async(
        lambda: _execute_notification(
            parsed_id,
            final_attempt=retries >= max_retries,
        ),
    )
    if outcome.status == "not_found":
        _logger.warning("notification_not_found")
        return {"status": "discarded"}
    if outcome.status == "retry" and retries < max_retries:
        countdown = get_settings().notifications_delivery_retry_backoff_seconds * (2**retries)
        raise self.retry(countdown=countdown)
    return {"status": outcome.status}


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
        storage = S3StorageAdapter(settings) if settings.s3_configured else None
        cancel_cutoff = datetime.now(UTC) - timedelta(
            seconds=min(settings.analysis_lease_seconds, _CANCEL_FINALIZE_SECONDS),
        )
        for record in await repository.list_stale_cancelling(cancel_cutoff):
            if storage is not None:
                with suppress(Exception):
                    await storage.delete(
                        build_analysis_report_key(
                            owner_id=record.owner_id,
                            analysis_id=record.id,
                        ),
                    )
            await repository.finalize_cancelled(
                record.id,
                event=AnalysisEvent(
                    analysis_id=record.id,
                    event_type=AnalysisEventType.CANCELLED,
                    payload={"reason": "cancel_timeout"},
                ),
            )
        return requeued
    finally:
        await engine.dispose()


@celery_app.task(name=PAYABLES_REMINDER_TASK)  # type: ignore[untyped-decorator]
def dispatch_payable_reminders() -> int:
    return run_async(_dispatch_payable_reminders)


async def _dispatch_payable_reminders() -> int:
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        repository = SqlAlchemyPayableReminderRepository(session_factory)
        result = await repository.create_due_reminders(
            datetime.now(UTC),
            lookback_days=settings.payables_reminder_lookback_days,
        )
        get_platform_metrics().record_notification("in_app", "created", result.created)
        _dispatch_notifications(result.notification_ids)
        return result.created
    finally:
        await engine.dispose()


@celery_app.task(name=PAYABLES_OVERDUE_TASK)  # type: ignore[untyped-decorator]
def mark_overdue_payables() -> int:
    return run_async(_mark_overdue_payables)


async def _mark_overdue_payables() -> int:
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        repository = SqlAlchemyPayableReminderRepository(session_factory)
        result = await repository.mark_overdue(datetime.now(UTC))
        get_platform_metrics().record_notification("in_app", "created", result.created)
        _dispatch_notifications(result.notification_ids)
        return result.created
    finally:
        await engine.dispose()


def _dispatch_notifications(notification_ids: tuple[UUID, ...]) -> None:
    if not notification_ids:
        return
    dispatcher = CeleryTaskDispatcher(celery_app)
    for notification_id in notification_ids:
        try:
            dispatcher.dispatch_notification(notification_id)
        except Exception:
            _logger.error("notification_dispatch_failed")
