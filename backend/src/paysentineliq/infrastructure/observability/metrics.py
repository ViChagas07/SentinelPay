import atexit
import contextlib
import os
import re
from pathlib import Path

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client import (
    multiprocess as prometheus_multiprocess,
)

KNOWN_QUEUES = (
    "analysis",
    "notifications",
    "scheduler",
    "analysis.dlq",
    "notifications.dlq",
    "scheduler.dlq",
)

_DOCUMENT_TYPES = frozenset({"boleto", "payslip", "receipt", "other"})
_BANDS = frozenset({"low", "attention", "medium", "high", "critical", "other"})
_STAGES = frozenset(
    {
        "load",
        "ingest",
        "guard",
        "classify",
        "boleto",
        "payslip",
        "receipt",
        "fraud",
        "rag",
        "interpret",
        "persist",
        "other",
    },
)
_LLM_OUTCOMES = frozenset({"success", "error", "retry", "other"})
_GUARDRAIL_LAYERS = frozenset(
    {
        "input_sanitization",
        "injection_patterns",
        "classifier",
        "output_validation",
        "judge",
        "other",
    },
)
_CHANNELS = frozenset({"email", "sms", "whatsapp", "in_app", "other"})
_NOTIFICATION_STATUSES = frozenset({"sent", "skipped", "failed", "created", "other"})
_CACHE_RESULTS = frozenset({"hit", "miss", "stale", "refresh", "error", "other"})
_RATE_LIMIT_SCOPES = frozenset({"ip", "user", "other"})

_UUID_SEGMENT = re.compile(
    r"/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
)
_NUMERIC_SEGMENT = re.compile(r"/(\d{4,})(?=/|$)")


class PlatformMetrics:
    def __init__(self, *, multiprocess: bool | None = None) -> None:
        multiprocess_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
        self._multiprocess = bool(multiprocess_dir) if multiprocess is None else multiprocess
        if self._multiprocess and not multiprocess_dir:
            raise ValueError("PROMETHEUS_MULTIPROC_DIR is required in multiprocess mode")
        if self._multiprocess and multiprocess_dir:
            Path(multiprocess_dir).mkdir(parents=True, exist_ok=True)
            atexit.register(_mark_process_dead, os.getpid())
        self._scrape_registry = CollectorRegistry()
        if self._multiprocess:
            prometheus_multiprocess.MultiProcessCollector(self._scrape_registry)  # type: ignore[no-untyped-call]
            creation_registry = CollectorRegistry()
        else:
            creation_registry = self._scrape_registry

        self.http_requests = Counter(
            "paysentineliq_http_requests_total",
            "HTTP requests handled.",
            ("method", "route", "status"),
            registry=creation_registry,
        )
        self.http_latency = Histogram(
            "paysentineliq_http_request_duration_seconds",
            "HTTP request duration.",
            ("method", "route"),
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
            registry=creation_registry,
        )
        self.http_rate_limited = Counter(
            "paysentineliq_http_429_total",
            "HTTP 429 responses.",
            ("scope",),
            registry=creation_registry,
        )
        self.analyses = Counter(
            "paysentineliq_analyses_total",
            "Completed analyses.",
            ("document_type", "band"),
            registry=creation_registry,
        )
        self.pipeline_stage_duration = Histogram(
            "paysentineliq_pipeline_stage_duration_seconds",
            "Pipeline stage duration.",
            ("stage", "document_type"),
            buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
            registry=creation_registry,
        )
        self.llm_requests = Counter(
            "paysentineliq_llm_requests_total",
            "LLM requests.",
            ("model", "outcome"),
            registry=creation_registry,
        )
        self.llm_latency = Histogram(
            "paysentineliq_llm_request_duration_seconds",
            "LLM request duration.",
            ("model",),
            buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
            registry=creation_registry,
        )
        self.guardrail_blocks = Counter(
            "paysentineliq_guardrail_blocks_total",
            "Guardrail findings by layer.",
            ("layer",),
            registry=creation_registry,
        )
        self.queue_depth = Gauge(
            "paysentineliq_queue_depth",
            "Broker queue depth.",
            ("queue",),
            multiprocess_mode="livesum",
            registry=creation_registry,
        )
        self.notifications = Counter(
            "paysentineliq_notifications_total",
            "Notification outcomes.",
            ("channel", "status"),
            registry=creation_registry,
        )
        self.cache_events = Counter(
            "paysentineliq_cache_events_total",
            "SWR cache outcomes.",
            ("result",),
            registry=creation_registry,
        )
        for queue in KNOWN_QUEUES:
            self.queue_depth.labels(queue=queue).set(0)

    @property
    def content_type(self) -> str:
        return CONTENT_TYPE_LATEST

    def render(self) -> bytes:
        return generate_latest(self._scrape_registry)

    def record_http_request(
        self,
        method: str,
        route: str,
        status: int,
        duration_seconds: float,
    ) -> None:
        safe_route = _safe_route(route)
        safe_method = method.upper() if method else "UNKNOWN"
        self.http_requests.labels(
            method=safe_method,
            route=safe_route,
            status=str(int(status)),
        ).inc()
        self.http_latency.labels(method=safe_method, route=safe_route).observe(
            max(0.0, duration_seconds),
        )

    def record_rate_limit(self, scope: str) -> None:
        self.http_rate_limited.labels(scope=_bounded(scope, _RATE_LIMIT_SCOPES)).inc()

    def record_analysis(self, document_type: str, band: str) -> None:
        self.analyses.labels(
            document_type=_bounded(document_type, _DOCUMENT_TYPES),
            band=_bounded(band, _BANDS),
        ).inc()

    def record_pipeline_stage(
        self,
        stage: str,
        document_type: str,
        duration_seconds: float,
    ) -> None:
        self.pipeline_stage_duration.labels(
            stage=_bounded(stage, _STAGES),
            document_type=_bounded(document_type, _DOCUMENT_TYPES),
        ).observe(max(0.0, duration_seconds))

    def record_llm(self, model: str, outcome: str, duration_seconds: float) -> None:
        safe_model = (model.strip() or "unknown")[:64]
        safe_outcome = _bounded(outcome, _LLM_OUTCOMES)
        self.llm_requests.labels(model=safe_model, outcome=safe_outcome).inc()
        self.llm_latency.labels(model=safe_model).observe(max(0.0, duration_seconds))

    def record_guardrail_block(self, layer: str) -> None:
        self.guardrail_blocks.labels(layer=_bounded(layer, _GUARDRAIL_LAYERS)).inc()

    def set_queue_depth(self, queue: str, depth: int) -> None:
        if queue not in KNOWN_QUEUES:
            return
        self.queue_depth.labels(queue=queue).set(max(0, int(depth)))

    def record_notification(self, channel: str, status: str, amount: int = 1) -> None:
        if amount <= 0:
            return
        self.notifications.labels(
            channel=_bounded(channel, _CHANNELS),
            status=_bounded(status, _NOTIFICATION_STATUSES),
        ).inc(amount)

    def record_cache(self, result: str) -> None:
        self.cache_events.labels(result=_bounded(result, _CACHE_RESULTS)).inc()


_metrics: PlatformMetrics | None = None


def get_platform_metrics() -> PlatformMetrics:
    global _metrics
    if _metrics is None:
        _metrics = PlatformMetrics()
    return _metrics


def set_platform_metrics(metrics: PlatformMetrics) -> None:
    global _metrics
    _metrics = metrics


def reset_platform_metrics() -> None:
    global _metrics
    _metrics = None


def _bounded(value: str, allowed: frozenset[str]) -> str:
    normalized = value.strip().lower()
    return normalized if normalized in allowed else "other"


def _safe_route(route: str) -> str:
    path = (route or "").split("?", 1)[0]
    if not path.startswith("/"):
        return "unmatched"
    path = _UUID_SEGMENT.sub("/{id}", path)
    path = _NUMERIC_SEGMENT.sub("/{id}", path)
    return path[:120]


def _mark_process_dead(pid: int) -> None:
    with contextlib.suppress(Exception):
        prometheus_multiprocess.mark_process_dead(pid)  # type: ignore[no-untyped-call]
