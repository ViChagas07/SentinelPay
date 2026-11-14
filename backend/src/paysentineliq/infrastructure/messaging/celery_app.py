from celery import Celery
from celery.signals import worker_ready
from kombu import Exchange, Queue

from paysentineliq.infrastructure.config import Settings, get_settings

ANALYSIS_QUEUE = "analysis"
NOTIFICATIONS_QUEUE = "notifications"
SCHEDULER_QUEUE = "scheduler"
DLX_NAME = "paysentineliq.dlx"

ANALYSIS_TASK = "paysentineliq.analysis.run"
NOTIFICATION_TASK = "paysentineliq.notifications.dispatch"
SWEEP_TASK = "paysentineliq.scheduler.sweep_stale_analyses"
PING_TASK = "paysentineliq.health.ping"

_TASK_ROUTES = {
    ANALYSIS_TASK: {
        "queue": ANALYSIS_QUEUE,
        "routing_key": ANALYSIS_QUEUE,
    },
    NOTIFICATION_TASK: {
        "queue": NOTIFICATIONS_QUEUE,
        "routing_key": NOTIFICATIONS_QUEUE,
    },
    SWEEP_TASK: {
        "queue": SCHEDULER_QUEUE,
        "routing_key": SCHEDULER_QUEUE,
    },
}


def _work_queue(name: str) -> Queue:
    return Queue(
        name,
        Exchange(name, type="direct", durable=True),
        routing_key=name,
        durable=True,
        queue_arguments={
            "x-dead-letter-exchange": DLX_NAME,
            "x-dead-letter-routing-key": f"{name}.dlq",
        },
    )


def _dead_letter_queue(name: str) -> Queue:
    return Queue(
        f"{name}.dlq",
        Exchange(DLX_NAME, type="direct", durable=True),
        routing_key=f"{name}.dlq",
        durable=True,
    )


def _ping() -> str:
    return "pong"


def build_celery_app(settings: Settings) -> Celery:
    app = Celery(
        "paysentineliq",
        broker=settings.rabbitmq_url,
        backend=settings.celery_result_backend,
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=("json",),
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        task_acks_on_failure_or_timeout=False,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1,
        task_default_queue=ANALYSIS_QUEUE,
        task_default_exchange=ANALYSIS_QUEUE,
        task_default_routing_key=ANALYSIS_QUEUE,
        task_queues=(
            _work_queue(ANALYSIS_QUEUE),
            _work_queue(NOTIFICATIONS_QUEUE),
            _work_queue(SCHEDULER_QUEUE),
            _dead_letter_queue(ANALYSIS_QUEUE),
            _dead_letter_queue(NOTIFICATIONS_QUEUE),
            _dead_letter_queue(SCHEDULER_QUEUE),
        ),
        task_routes=_TASK_ROUTES,
        task_soft_time_limit=settings.celery_task_soft_time_limit_seconds,
        task_time_limit=settings.celery_task_time_limit_seconds,
        task_annotations={
            ANALYSIS_TASK: {
                "max_retries": settings.analysis_task_max_retries,
                "retry_backoff": True,
                "retry_jitter": True,
            },
        },
        task_always_eager=settings.celery_task_always_eager,
        task_eager_propagates=settings.celery_task_always_eager,
        imports=("paysentineliq.infrastructure.messaging.tasks",),
        result_expires=3600,
        broker_connection_retry_on_startup=True,
        broker_transport_options={"confirm_publish": True},
        beat_schedule={
            "sweep-stale-analyses": {
                "task": SWEEP_TASK,
                "schedule": settings.analysis_stale_sweep_seconds,
                "options": {"queue": SCHEDULER_QUEUE},
            },
        },
    )
    app.task(name=PING_TASK)(_ping)
    return app


celery_app = build_celery_app(get_settings())


@worker_ready.connect  # type: ignore[untyped-decorator]
def _declare_dead_letter_queues(sender: Celery, **_: object) -> None:
    with sender.connection_for_write() as connection:
        channel = connection.default_channel
        for name in (ANALYSIS_QUEUE, NOTIFICATIONS_QUEUE, SCHEDULER_QUEUE):
            _dead_letter_queue(name)(channel).declare()
