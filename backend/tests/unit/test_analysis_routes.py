from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from paysentineliq.application.commands.create_analysis import (
    CreateAnalysisCommand,
    CreatedAnalysis,
)
from paysentineliq.application.errors import AnalysisQuotaExceededError
from paysentineliq.domain.analysis import AnalysisStatus
from paysentineliq.domain.document import DocumentKind
from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.interface.api.dependencies import (
    get_create_analysis_handler,
    get_current_user,
)
from paysentineliq.interface.api.main import create_app

pytestmark = pytest.mark.unit

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


def _app(handler: FakeHandler) -> Any:
    app = create_app(Settings(app_env="local"))
    app.dependency_overrides[get_current_user] = lambda: _USER
    app.dependency_overrides[get_create_analysis_handler] = lambda: handler
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


async def test_post_analysis_rejects_receipt_kind() -> None:
    handler = FakeHandler()
    response = await _post(_app(handler), kind="receipt")

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
