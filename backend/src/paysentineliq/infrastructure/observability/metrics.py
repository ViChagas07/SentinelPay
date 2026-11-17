import atexit
import contextlib
import logging
import os
import re
from pathlib import Path
from typing import Any

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
from prometheus_client.metrics_core import Metric

_logger = logging.getLogger("paysentineliq")

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
_RETRIEVAL_STAGES = frozenset(
    {"embed", "dense", "sparse", "fusion", "stage1", "rerank", "total", "other"},
)
_RETRIEVAL_CANDIDATE_STAGES = frozenset(
    {"dense", "sparse", "fused", "stage1", "reranked", "other"},
)
_RETRIEVAL_SCORE_STAGES = frozenset({"stage1", "reranked", "other"})
_RERANK_OUTCOMES = frozenset(
    {"success", "disabled", "timeout", "error", "empty", "unavailable", "other"},
)

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
        self._scrape_registry = CollectorRegistry()
        if self._multiprocess and multiprocess_dir:
            Path(multiprocess_dir).mkdir(parents=True, exist_ok=True)
            atexit.register(_mark_process_dead, os.getpid())
            scrape_dirs = [
                directory.strip()
                for directory in os.environ.get(
                    "PROMETHEUS_MULTIPROC_SCRAPE_DIRS",
                    multiprocess_dir,
                ).split(",")
                if directory.strip()
            ]
            self._scrape_registry.register(
                _MergedMultiProcessCollector(scrape_dirs),
            )
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
        self.retrieval_stage_duration = Histogram(
            "paysentineliq_retrieval_stage_duration_seconds",
            "Retrieval stage duration.",
            ("stage",),
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
            registry=creation_registry,
        )
        self.retrieval_candidates = Histogram(
            "paysentineliq_retrieval_candidates",
            "Retrieval candidates per stage.",
            ("stage",),
            buckets=(0, 1, 2, 4, 8, 16, 25, 50, 100),
            registry=creation_registry,
        )
        self.retrieval_scores = Histogram(
            "paysentineliq_retrieval_scores",
            "Retrieval scores before and after rerank.",
            ("stage",),
            buckets=(0.0, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0),
            registry=creation_registry,
        )
        self.retrieval_rerank = Counter(
            "paysentineliq_retrieval_rerank_total",
            "Rerank outcomes.",
            ("outcome",),
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
        for result in _CACHE_RESULTS - {"other"}:
            self.cache_events.labels(result=result).inc(0)
        for scope in _RATE_LIMIT_SCOPES - {"other"}:
            self.http_rate_limited.labels(scope=scope).inc(0)
        for stage in _RETRIEVAL_STAGES - {"other"}:
            self.retrieval_stage_duration.labels(stage=stage)
        for stage in _RETRIEVAL_CANDIDATE_STAGES - {"other"}:
            self.retrieval_candidates.labels(stage=stage)
        for stage in _RETRIEVAL_SCORE_STAGES - {"other"}:
            self.retrieval_scores.labels(stage=stage)
        for outcome in _RERANK_OUTCOMES - {"other"}:
            self.retrieval_rerank.labels(outcome=outcome).inc(0)
        for layer in _GUARDRAIL_LAYERS - {"other"}:
            self.guardrail_blocks.labels(layer=layer).inc(0)
        for channel in _CHANNELS - {"other"}:
            for status in _NOTIFICATION_STATUSES - {"other"}:
                self.notifications.labels(channel=channel, status=status).inc(0)

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

    def record_llm(
        self,
        model: str,
        outcome: str,
        duration_seconds: float | None = None,
    ) -> None:
        safe_model = (model.strip() or "unknown")[:64]
        safe_outcome = _bounded(outcome, _LLM_OUTCOMES)
        self.llm_requests.labels(model=safe_model, outcome=safe_outcome).inc()
        if duration_seconds is not None:
            self.llm_latency.labels(model=safe_model).observe(
                max(0.0, duration_seconds),
            )

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

    def record_retrieval_stage(self, stage: str, duration_seconds: float) -> None:
        self.retrieval_stage_duration.labels(
            stage=_bounded(stage, _RETRIEVAL_STAGES),
        ).observe(max(0.0, duration_seconds))

    def record_retrieval_candidates(self, stage: str, count: int) -> None:
        self.retrieval_candidates.labels(
            stage=_bounded(stage, _RETRIEVAL_CANDIDATE_STAGES),
        ).observe(max(0, int(count)))

    def record_retrieval_score(self, stage: str, score: float) -> None:
        self.retrieval_scores.labels(
            stage=_bounded(stage, _RETRIEVAL_SCORE_STAGES),
        ).observe(min(1.0, max(0.0, float(score))))

    def record_rerank_outcome(self, outcome: str) -> None:
        self.retrieval_rerank.labels(
            outcome=_bounded(outcome, _RERANK_OUTCOMES),
        ).inc()


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


class _MergedMultiProcessCollector:
    def __init__(self, directories: list[str]) -> None:
        self._directories = directories
        self._logged_failures: set[str] = set()

    def collect(self) -> list[Metric]:
        merged: dict[
            tuple[str, str],
            tuple[str, dict[tuple[str, tuple[tuple[str, str], ...]], Any]],
        ] = {}
        for directory in self._directories:
            try:
                collector = prometheus_multiprocess.MultiProcessCollector(  # type: ignore[no-untyped-call]
                    CollectorRegistry(),
                    path=directory,
                )
                metrics = list(collector.collect())  # type: ignore[no-untyped-call]
            except Exception:
                if directory not in self._logged_failures:
                    _logger.warning("prometheus_multiprocess_dir_unreadable")
                    self._logged_failures.add(directory)
                continue
            self._logged_failures.discard(directory)
            for metric in metrics:
                _, samples = merged.setdefault(
                    (metric.name, metric.type),
                    (metric.documentation, {}),
                )
                for sample in metric.samples:
                    key = (sample.name, tuple(sorted(sample.labels.items())))
                    existing = samples.get(key)
                    if existing is None:
                        samples[key] = sample
                    else:
                        samples[key] = existing._replace(
                            value=existing.value + sample.value,
                        )
        output: list[Metric] = []
        for (name, metric_type), (documentation, samples) in merged.items():
            metric = Metric(name, documentation, metric_type)
            metric.samples.extend(samples.values())
            output.append(metric)
        return output


def _mark_process_dead(pid: int) -> None:
    with contextlib.suppress(Exception):
        prometheus_multiprocess.mark_process_dead(pid)  # type: ignore[no-untyped-call]
