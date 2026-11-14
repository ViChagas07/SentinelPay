from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from paysentineliq.application.commands.create_analysis import (
    CreateAnalysisCommand,
    CreatedAnalysis,
)
from paysentineliq.application.errors import AnalysisNotFoundError, AnalysisQuotaExceededError
from paysentineliq.application.queries.analyses import (
    AnalysisDetailDTO,
    AnalysisEvidenceDTO,
    AnalysisListDTO,
    AnalysisListItemDTO,
    AnalysisResultDTO,
)
from paysentineliq.domain.analysis import AnalysisStatus
from paysentineliq.domain.document import DocumentKind
from paysentineliq.domain.scoring import RiskBand
from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.interface.api.dependencies import (
    get_analysis_detail_query,
    get_analysis_list_query,
    get_create_analysis_handler,
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


class FakeHandler:
    def __init__(
        self,
        *,
        replayed: bool = False,
        error: Exception | None = None,
    ) -> None:
        self.commands: list[CreateAnalysisCommand] = []
        self.contents: list[bytes] = []
        self._replayed = replayed
        self._error = error

    async def handle(self, command: CreateAnalysisCommand) -> CreatedAnalysis:
        self.commands.append(command)
        self.contents.append(command.stream.read())
        if self._error is not None:
            raise self._error
        return CreatedAnalysis(
            analysis_id=uuid4(),
            document_id=uuid4(),
            status=AnalysisStatus.QUEUED,
            replayed=self._replayed,
        )


class FakeDetailHandler:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[UUID, UUID]] = []

    async def handle(self, analysis_id: UUID, owner_id: UUID) -> AnalysisDetailDTO:
        self.calls.append((analysis_id, owner_id))
        if self.error is not None:
            raise self.error
        return AnalysisDetailDTO(
            id=analysis_id,
            status=AnalysisStatus.COMPLETED,
            kind="boleto",
            created_at=_NOW,
            updated_at=_NOW,
            error_code=None,
            result_available=True,
            result=AnalysisResultDTO(
                score=80,
                band=RiskBand.HIGH,
                base_score=78,
                llm_adjustment=2,
                evidence=(
                    AnalysisEvidenceDTO(
                        rule_id="dv_invalid",
                        severity="critical",
                        weight=70,
                        message_key="boleto.dv_invalid",
                        source="febraban-v1",
                    ),
                ),
                justification="DV invalido.",
                inconsistencies=("Sugestao.",),
                degradation_flags=(),
            ),
        )


class FakeListHandler:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, int, str | None]] = []

    async def handle(
        self,
        owner_id: UUID,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> AnalysisListDTO:
        self.calls.append((owner_id, limit, cursor))
        return AnalysisListDTO(
            items=(
                AnalysisListItemDTO(
                    id=uuid4(),
                    status=AnalysisStatus.COMPLETED,
                    kind="boleto",
                    score=80,
                    band=RiskBand.HIGH,
                    error_code=None,
                    created_at=_NOW,
                    updated_at=_NOW,
                ),
            ),
            next_cursor="next-cursor",
        )


def _app(
    handler: FakeHandler | None = None,
    *,
    detail: FakeDetailHandler | None = None,
    listing: FakeListHandler | None = None,
) -> Any:
    app = create_app(Settings(app_env="local"))
    app.dependency_overrides[get_current_user] = lambda: _USER
    if handler is not None:
        app.dependency_overrides[get_create_analysis_handler] = lambda: handler
    if detail is not None:
        app.dependency_overrides[get_analysis_detail_query] = lambda: detail
    if listing is not None:
        app.dependency_overrides[get_analysis_list_query] = lambda: listing
    return app


async def _post(
    app: Any,
    *,
    kind: str = "boleto",
    idempotency_key: str | None = None,
) -> httpx.Response:
    headers = {}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            "/api/v1/analyses",
            data={"kind": kind},
            files={"file": ("boleto.pdf", b"%PDF-1.4 synthetic", "application/pdf")},
            headers=headers,
        )


async def _get(app: Any, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


async def test_post_analysis_returns_202_and_maps_kind() -> None:
    handler = FakeHandler()
    response = await _post(_app(handler), idempotency_key="idem-12345678")

    assert response.status_code == 202
    payload = response.json()
    assert UUID(payload["analysis_id"])
    assert payload["status"] == "queued"
    assert handler.commands[0].owner_id == _USER.id
    assert handler.commands[0].kind is DocumentKind.BANK_SLIP
    assert handler.commands[0].idempotency_key == "idem-12345678"
    assert handler.contents[0] == b"%PDF-1.4 synthetic"


async def test_post_analysis_maps_payslip() -> None:
    handler = FakeHandler()
    response = await _post(_app(handler), kind="payslip")

    assert response.status_code == 202
    assert handler.commands[0].kind is DocumentKind.PAYSLIP


async def test_post_analysis_accepts_receipt_kind() -> None:
    handler = FakeHandler()
    response = await _post(_app(handler), kind="receipt")

    assert response.status_code == 202
    assert handler.commands[0].kind is DocumentKind.RECEIPT


async def test_post_analysis_rejects_unknown_kind() -> None:
    handler = FakeHandler()
    response = await _post(_app(handler), kind="unknown")

    assert response.status_code == 422
    assert handler.commands == []


async def test_post_analysis_marks_idempotent_replay() -> None:
    handler = FakeHandler(replayed=True)
    response = await _post(_app(handler), idempotency_key="idem-12345678")

    assert response.status_code == 202
    assert response.headers["Idempotency-Replayed"] == "true"


async def test_post_analysis_maps_quota_error_to_429() -> None:
    handler = FakeHandler(error=AnalysisQuotaExceededError())
    response = await _post(_app(handler))

    assert response.status_code == 429
    assert response.json()["code"] == "analysis_quota_exceeded"


async def test_get_analysis_returns_result() -> None:
    detail = FakeDetailHandler()
    analysis_id = uuid4()

    response = await _get(_app(detail=detail), f"/api/v1/analyses/{analysis_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["result"]["score"] == 80
    assert payload["result"]["evidence"][0]["rule_id"] == "dv_invalid"
    assert payload["result"]["justification"] == "DV invalido."
    assert detail.calls[0][0] == analysis_id
    assert detail.calls[0][1] == _USER.id


async def test_get_analysis_of_other_owner_is_404() -> None:
    detail = FakeDetailHandler(error=AnalysisNotFoundError())

    response = await _get(_app(detail=detail), f"/api/v1/analyses/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["code"] == "analysis_not_found"


async def test_list_analyses_returns_cursor_page() -> None:
    listing = FakeListHandler()

    response = await _get(
        _app(listing=listing),
        "/api/v1/analyses?limit=1&cursor=abc",
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["score"] == 80
    assert payload["next_cursor"] == "next-cursor"
    assert listing.calls[0][1:] == (1, "abc")


async def test_list_analyses_rejects_oversized_limit() -> None:
    response = await _get(_app(listing=FakeListHandler()), "/api/v1/analyses?limit=51")

    assert response.status_code == 422
