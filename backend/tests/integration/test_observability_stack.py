import asyncio
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paysentineliq.infrastructure.db.models import (
    AnalysisEventModel,
    AnalysisModel,
    DocumentModel,
    NotificationDeliveryModel,
    NotificationModel,
    PayableModel,
    UserModel,
)
from paysentineliq.interface.api.routes.analyses import AnalysisKind
from tests.integration.test_analysis_queue_e2e import (
    _API_URL,
    _auth,
    _create_user,
    _pdf,
    _wait_for_terminal,
)
from tests.support.boleto_factory import build_boleto

pytestmark = pytest.mark.observability

_METRICS_TOKEN = os.environ.get("METRICS_TOKEN", "CHANGE_ME")
_GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3001")
_GRAFANA_USER = os.environ.get("GRAFANA_ADMIN_USER", "admin")
_GRAFANA_PASSWORD = os.environ.get("GRAFANA_ADMIN_PASSWORD", "CHANGE_ME")
_PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://127.0.0.1:9090")
_TEMPO_URL = os.environ.get("TEMPO_URL", "http://127.0.0.1:3200")


async def test_dashboards_and_metrics_show_a_synthetic_analysis() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owners: list[UUID] = []
    analyses: list[UUID] = []
    try:
        owner = await _create_user(factory, "observability")
        owners = [owner.id]
        boleto = build_boleto()
        async with httpx.AsyncClient(base_url=_API_URL, timeout=90) as api:
            analysis_id = await _upload(api, _auth(owner), boleto.ocr_text())
            analyses.append(analysis_id)
            detail = await _wait_for_terminal(
                api,
                analysis_id,
                _auth(owner),
                timeout_seconds=180,
            )
            assert detail["status"] in {"completed", "degraded"}

            metrics = await _wait_for_metrics(api)
            assert "paysentineliq_http_requests_total" in metrics
            assert "paysentineliq_analyses_total" in metrics
            assert "paysentineliq_pipeline_stage_duration_seconds_count" in metrics
            assert "paysentineliq_llm_requests_total" in metrics
            assert "paysentineliq_queue_depth" in metrics
            assert "paysentineliq_notifications_total" in metrics
            assert "paysentineliq_cache_events_total" in metrics
            assert owner.email not in metrics
            assert "user_id=" not in metrics
            assert "document_id=" not in metrics

        await _wait_for_prometheus()
        await _assert_grafana_provisioned()
        await _assert_tempo_has_traces(
            forbidden_values=(owner.email, str(analysis_id)),
        )
    finally:
        async with factory() as session:
            if owners:
                await session.execute(
                    delete(NotificationDeliveryModel).where(
                        NotificationDeliveryModel.notification_id.in_(
                            select(NotificationModel.id).where(
                                NotificationModel.owner_id.in_(owners),
                            ),
                        ),
                    ),
                )
                await session.execute(
                    delete(NotificationModel).where(NotificationModel.owner_id.in_(owners)),
                )
                await session.execute(
                    delete(PayableModel).where(PayableModel.owner_id.in_(owners)),
                )
            if analyses:
                await session.execute(
                    delete(AnalysisEventModel).where(
                        AnalysisEventModel.analysis_id.in_(analyses),
                    ),
                )
                await session.execute(
                    delete(AnalysisModel).where(AnalysisModel.id.in_(analyses)),
                )
                await session.execute(
                    delete(DocumentModel).where(DocumentModel.owner_id.in_(owners)),
                )
            if owners:
                await session.execute(delete(UserModel).where(UserModel.id.in_(owners)))
            await session.commit()
        await engine.dispose()


async def _upload(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    text: str,
) -> UUID:
    response = await client.post(
        "/api/v1/analyses",
        data={"kind": AnalysisKind.BOLETO.value},
        files={"file": ("boleto.pdf", _pdf(text), "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    return UUID(response.json()["analysis_id"])


async def _wait_for_metrics(client: httpx.AsyncClient) -> str:
    deadline = time.monotonic() + 90
    last = ""
    while time.monotonic() < deadline:
        response = await client.get(
            "/metrics",
            headers={"Authorization": f"Bearer {_METRICS_TOKEN}"},
        )
        if response.status_code == 200:
            last = response.text
            if "paysentineliq_analyses_total{" in last:
                return last
        await asyncio.sleep(1)
    raise AssertionError(f"analysis metrics did not appear: {last[:1000]}")


async def _wait_for_prometheus() -> None:
    deadline = time.monotonic() + 90
    async with httpx.AsyncClient(base_url=_PROMETHEUS_URL, timeout=10) as client:
        while time.monotonic() < deadline:
            response = await client.get(
                "/api/v1/query",
                params={"query": "sum(paysentineliq_analyses_total)"},
            )
            if response.status_code == 200:
                result = response.json().get("data", {}).get("result", [])
                if result and float(result[0]["value"][1]) > 0:
                    return
            await asyncio.sleep(2)
    raise AssertionError("Prometheus did not ingest paysentineliq_analyses_total")


async def _assert_grafana_provisioned() -> None:
    auth = httpx.BasicAuth(_GRAFANA_USER, _GRAFANA_PASSWORD)
    deadline = time.monotonic() + 60
    async with httpx.AsyncClient(base_url=_GRAFANA_URL, timeout=10) as client:
        while time.monotonic() < deadline:
            health = await client.get("/api/health")
            if health.status_code == 200:
                break
            await asyncio.sleep(2)
        else:
            raise AssertionError("Grafana did not become healthy")

        datasources = await client.get("/api/datasources", auth=auth)
        assert datasources.status_code == 200, datasources.text
        names = {item["name"] for item in datasources.json()}
        assert {"Prometheus", "Tempo"} <= names

        search = await client.get("/api/search", params={"tag": "paysentineliq"}, auth=auth)
        assert search.status_code == 200, search.text
        titles = {item["title"] for item in search.json()}
        assert {
            "PaySentinelIQ / API",
            "PaySentinelIQ / AI Pipeline",
            "PaySentinelIQ / Queues and Notifications",
            "PaySentinelIQ / Security",
        } <= titles


async def _assert_tempo_has_traces(
    *,
    forbidden_values: tuple[str, ...],
) -> None:
    deadline = time.monotonic() + 90
    end = datetime.now(UTC) + timedelta(minutes=1)
    start = end - timedelta(minutes=30)
    async with httpx.AsyncClient(base_url=_TEMPO_URL, timeout=30) as client:
        while time.monotonic() < deadline:
            ready = await client.get("/ready")
            if ready.status_code == 200:
                worker = await _search_traces(client, "paysentineliq-worker", start, end)
                api = await _search_traces(client, "paysentineliq-api", start, end)
                if worker and api:
                    trace_id = api[0].get("traceID")
                    if isinstance(trace_id, str):
                        await _assert_trace_detail_is_pii_free(
                            client,
                            trace_id,
                            forbidden_values=forbidden_values,
                        )
                        return
            await asyncio.sleep(2)
    raise AssertionError("Tempo did not receive worker and API traces")


async def _search_traces(
    client: httpx.AsyncClient,
    service: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    response = await client.get(
        "/api/search",
        params={
            "tags": f"service.name={service}",
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
            "limit": 20,
        },
    )
    if response.status_code != 200:
        return []
    traces = response.json().get("traces", [])
    return [item for item in traces if isinstance(item, dict)] if isinstance(traces, list) else []


async def _assert_trace_detail_is_pii_free(
    client: httpx.AsyncClient,
    trace_id: str,
    *,
    forbidden_values: tuple[str, ...],
) -> None:
    response = await client.get(f"/api/traces/{trace_id}")
    assert response.status_code == 200, response.text
    dumped = response.text
    for forbidden in (*forbidden_values, "529.982", "document.text"):
        assert forbidden not in dumped, f"trace leaked {forbidden}"
