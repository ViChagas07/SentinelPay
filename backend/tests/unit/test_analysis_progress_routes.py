from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from paysentineliq.application.commands.cancel_analysis import AnalysisCancellationDTO
from paysentineliq.application.errors import (
    AnalysisNotCancellableError,
    AnalysisNotFoundError,
)
from paysentineliq.application.ports.analysis_read_repository import AnalysisSummary
from paysentineliq.application.queries.analyses import AnalysisDetailDTO, AnalysisProgressDTO
from paysentineliq.domain.analysis import AnalysisDocumentType, AnalysisStatus
from paysentineliq.domain.analysis_progress import AnalysisStage
from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.interface.api.dependencies import (
    get_analysis_detail_query,
    get_analysis_read_repository,
    get_cancel_analysis_handler,
    get_current_user,
)
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_USER = User(
    id=uuid4(),
    google_sub="google-sub",
    email="user@example.com",
    name="User",
    preferred_locale="pt-BR",
    timezone="America/Sao_Paulo",
    role=Role.USER,
)


class FakeCancelHandler:
    def __init__(
        self,
        *,
        status: AnalysisStatus = AnalysisStatus.CANCELLING,
        error: Exception | None = None,
    ) -> None:
        self.status = status
        self.error = error
        self.calls: list[tuple[UUID, UUID]] = []

    async def handle(self, analysis_id: UUID, owner_id: UUID) -> AnalysisCancellationDTO:
        self.calls.append((analysis_id, owner_id))
        if self.error is not None:
            raise self.error
        return AnalysisCancellationDTO(analysis_id=analysis_id, status=self.status)


class FakeReadRepository:
    def __init__(self, summary: AnalysisSummary | None) -> None:
        self.summary = summary

    async def get_for_owner(
        self,
        analysis_id: UUID,
        owner_id: UUID,
    ) -> AnalysisSummary | None:
        return self.summary


class FakeDetailHandler:
    def __init__(self, detail: AnalysisDetailDTO) -> None:
        self.detail = detail

    async def handle(self, analysis_id: UUID, owner_id: UUID) -> AnalysisDetailDTO:
        return self.detail


def _summary(status: AnalysisStatus = AnalysisStatus.RUNNING) -> AnalysisSummary:
    return AnalysisSummary(
        id=uuid4(),
        owner_id=_USER.id,
        document_id=uuid4(),
        document_type=AnalysisDocumentType.BOLETO,
        status=status,
        score=87 if status is AnalysisStatus.COMPLETED else None,
        band=None,
        error_code=None,
        report_s3_key=None,
        created_at=_NOW,
        updated_at=_NOW,
        progress_percent=100 if status is AnalysisStatus.COMPLETED else 70,
        current_stage=(
            AnalysisStage.PERSISTENCE if status is AnalysisStatus.COMPLETED else AnalysisStage.RAG
        ),
        stage_detail="Resultado salvo" if status is AnalysisStatus.COMPLETED else "Reranqueando",
        stage_started_at=_NOW,
    )


def _app(
    *,
    cancel: FakeCancelHandler | None = None,
    repository: FakeReadRepository | None = None,
    detail: FakeDetailHandler | None = None,
) -> Any:
    app = create_app(Settings(app_env="local"))
    app.dependency_overrides[get_current_user] = lambda: _USER
    if cancel is not None:
        app.dependency_overrides[get_cancel_analysis_handler] = lambda: cancel
    if repository is not None:
        app.dependency_overrides[get_analysis_read_repository] = lambda: repository
    if detail is not None:
        app.dependency_overrides[get_analysis_detail_query] = lambda: detail
    return app


async def _request(
    app: Any,
    method: str,
    path: str,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path)


async def test_cancel_analysis_returns_cancelling_for_owner() -> None:
    handler = FakeCancelHandler()
    analysis_id = uuid4()

    response = await _request(
        _app(cancel=handler),
        "POST",
        f"/api/v1/analyses/{analysis_id}/cancel",
    )

    assert response.status_code == 202
    assert response.json() == {
        "analysis_id": str(analysis_id),
        "status": "cancelling",
    }
    assert handler.calls == [(analysis_id, _USER.id)]


async def test_cancel_completed_analysis_returns_conflict() -> None:
    response = await _request(
        _app(cancel=FakeCancelHandler(error=AnalysisNotCancellableError())),
        "POST",
        f"/api/v1/analyses/{uuid4()}/cancel",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "analysis_not_cancellable"


async def test_cancel_missing_analysis_returns_not_found() -> None:
    response = await _request(
        _app(cancel=FakeCancelHandler(error=AnalysisNotFoundError())),
        "POST",
        f"/api/v1/analyses/{uuid4()}/cancel",
    )

    assert response.status_code == 404
    assert response.json()["code"] == "analysis_not_found"


async def test_events_stream_sends_snapshot_and_done_for_terminal_analysis() -> None:
    summary = _summary(AnalysisStatus.COMPLETED)
    response = await _request(
        _app(repository=FakeReadRepository(summary)),
        "GET",
        f"/api/v1/analyses/{summary.id}/events",
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: progress" in response.text
    assert "event: done" in response.text
    assert '"percent":100' in response.text
    assert '"status":"completed"' in response.text


async def test_events_stream_returns_not_found_for_other_owner() -> None:
    response = await _request(
        _app(repository=FakeReadRepository(None)),
        "GET",
        f"/api/v1/analyses/{uuid4()}/events",
    )

    assert response.status_code == 404


async def test_detail_exposes_progress_stage_and_cancel_timestamp() -> None:
    analysis_id = uuid4()
    detail = AnalysisDetailDTO(
        id=analysis_id,
        status=AnalysisStatus.RUNNING,
        kind="boleto",
        created_at=_NOW,
        updated_at=_NOW,
        error_code=None,
        result_available=False,
        result=None,
        progress=AnalysisProgressDTO(
            percent=70,
            stage=AnalysisStage.RAG,
            detail="Reranqueando",
            started_at=_NOW,
            indeterminate=True,
        ),
    )

    response = await _request(
        _app(detail=FakeDetailHandler(detail)),
        "GET",
        f"/api/v1/analyses/{analysis_id}",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["progress"] == {
        "percent": 70,
        "stage": "rag",
        "detail": "Reranqueando",
        "started_at": "2026-01-01T00:00:00Z",
        "indeterminate": True,
    }
    assert payload["cancelled_at"] is None
