import logging
from uuid import UUID, uuid4

from celery import Celery

from paysentineliq.application.errors import TaskDispatchError
from paysentineliq.infrastructure.logging import get_request_id
from paysentineliq.infrastructure.messaging.celery_app import (
    ANALYSIS_QUEUE,
    ANALYSIS_TASK,
    NOTIFICATION_TASK,
    NOTIFICATIONS_QUEUE,
)

_logger = logging.getLogger("paysentineliq")

_RETRY_POLICY = {
    "max_retries": 3,
    "interval_start": 0,
    "interval_step": 1,
    "interval_max": 5,
}


class CeleryTaskDispatcher:
    def __init__(self, app: Celery) -> None:
        self._app = app

    def dispatch_analysis(self, analysis_id: UUID, *, locale: str = "pt") -> None:
        try:
            self._app.send_task(
                ANALYSIS_TASK,
                args=[str(analysis_id), locale],
                queue=ANALYSIS_QUEUE,
                retry=True,
                retry_policy=_RETRY_POLICY,
                headers=self._headers(),
            )
        except Exception as exc:
            _logger.error("analysis_dispatch_failed")
            raise TaskDispatchError() from exc

    def dispatch_notification(self, notification_id: UUID) -> None:
        try:
            self._app.send_task(
                NOTIFICATION_TASK,
                args=[str(notification_id)],
                queue=NOTIFICATIONS_QUEUE,
                retry=True,
                retry_policy=_RETRY_POLICY,
                headers=self._headers(),
            )
        except Exception as exc:
            _logger.error("notification_dispatch_failed")
            raise TaskDispatchError() from exc

    @staticmethod
    def _headers() -> dict[str, str]:
        return {"request_id": get_request_id() or str(uuid4())}
