from datetime import UTC, datetime
from types import TracebackType
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from paysentineliq.application.errors import (
    DangerousPdfError,
    DocumentNotFoundError,
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
)
from paysentineliq.application.use_cases.documents import UploadedDocument
from paysentineliq.domain.document import Document, DocumentKind
from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService
from paysentineliq.interface.api.dependencies import (
    get_auth_unit_of_work,
    get_document_service,
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
_DOCUMENT = Document(
    id=uuid4(),
    owner_id=_USER.id,
    kind=DocumentKind.BANK_SLIP,
    s3_key=f"users/{_USER.id}/bank_slip/{uuid4()}/original.pdf",
    sha256="a" * 64,
    size=10,
    content_type="application/pdf",
    original_name_sanitized="boleto.pdf",
    created_at=_NOW,
)


class FakeUsers:
    async def get_by_id(self, user_id: UUID) -> User | None:
        return _USER if user_id == _USER.id else None


class FakeAuthUow:
    def __init__(self) -> None:
        self.users = FakeUsers()

    async def __aenter__(self) -> "FakeAuthUow":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FakeRevokedStore:
    async def revoke(self, jti: str, expires_at: int) -> None:
        return None

    async def is_revoked(self, jti: str) -> bool:
        return False


class FakeDocumentService:
    def __init__(self) -> None:
        self.upload_error: Exception | None = None
        self.download_error: Exception | None = None
        self.uploaded: UploadedDocument | None = None
        self.url = "https://storage.example/short-url"

    async def upload(
        self,
        *,
        owner_id: UUID,
        kind: DocumentKind,
        original_name: str | None,
        stream: Any,
    ) -> UploadedDocument:
        if self.upload_error is not None:
            raise self.upload_error
        analysis_id = uuid4()
        document = Document(
            id=_DOCUMENT.id,
            owner_id=owner_id,
            kind=kind,
            s3_key=(f"users/{owner_id}/{kind.value}/{analysis_id}/original.pdf"),
            sha256=_DOCUMENT.sha256,
            size=_DOCUMENT.size,
            content_type=_DOCUMENT.content_type,
            original_name_sanitized="boleto.pdf",
            created_at=_NOW,
        )
        self.uploaded = UploadedDocument(
            document=document,
            analysis_id=analysis_id,
        )
        return self.uploaded

    async def get_download_url(
        self,
        *,
        owner_id: UUID,
        document_id: UUID,
    ) -> tuple[str, int]:
        if self.download_error is not None:
            raise self.download_error
        return self.url, 60


def _app(
    service: FakeDocumentService | None = None,
) -> tuple[FastAPI, str, FakeDocumentService]:
    settings = Settings(
        app_env="local",
        jwt_secret="s" * 64,
        security_hash_secret="h" * 32,
    )
    app = create_app(settings)
    token_service = JwtAccessTokenService(
        secret=settings.jwt_secret,
        ttl_minutes=15,
    )
    app.state.token_service = token_service
    app.state.revoked_tokens = FakeRevokedStore()
    fake_service = service or FakeDocumentService()
    app.dependency_overrides[get_auth_unit_of_work] = FakeAuthUow
    app.dependency_overrides[get_document_service] = lambda: fake_service
    token = token_service.issue(_USER).token
    return app, token, fake_service


async def _upload(
    app: FastAPI,
    token: str | None,
    *,
    data: bytes = b"%PDF-1.4 fake",
    filename: str = "fake.pdf",
    kind: str = "bank_slip",
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.post(
            "/api/v1/documents/upload",
            headers=headers,
            data={"kind": kind},
            files={"file": (filename, data, "application/pdf")},
        )


async def test_upload_requires_authentication() -> None:
    app, _, _ = _app()

    response = await _upload(app, None)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


async def test_valid_upload_returns_created_document() -> None:
    app, token, service = _app()

    response = await _upload(
        app,
        token,
        filename="../../etc/boleto.pdf",
    )

    assert response.status_code == 201
    assert service.uploaded is not None
    body = response.json()
    assert body["kind"] == "bank_slip"
    assert body["analysis_id"] == str(service.uploaded.analysis_id)
    assert body["original_name_sanitized"] == "boleto.pdf"


async def test_upload_too_large_returns_problem_json() -> None:
    app, token, service = _app()
    service.upload_error = UploadTooLargeError()

    response = await _upload(app, token)

    assert response.status_code == 413
    assert response.json()["code"] == "upload_too_large"


async def test_unsupported_document_returns_problem_json() -> None:
    app, token, service = _app()
    service.upload_error = UnsupportedDocumentTypeError()

    response = await _upload(app, token, data=b"not a document")

    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_document_type"


async def test_dangerous_pdf_returns_evidence() -> None:
    app, token, service = _app()
    service.upload_error = DangerousPdfError(("javascript",))

    response = await _upload(app, token)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "pdf_active_content"
    assert body["evidence"] == ["javascript"]


async def test_download_url_is_short_and_scoped() -> None:
    app, token, _ = _app()

    response = await _request(
        app,
        "GET",
        f"/api/v1/documents/{_DOCUMENT.id}/url",
        token,
    )

    assert response.status_code == 200
    assert response.json() == {
        "url": "https://storage.example/short-url",
        "expires_in": 60,
    }


async def test_download_url_of_other_owner_is_not_found() -> None:
    app, token, service = _app()
    service.download_error = DocumentNotFoundError()

    response = await _request(
        app,
        "GET",
        f"/api/v1/documents/{_DOCUMENT.id}/url",
        token,
    )

    assert response.status_code == 404
    assert response.json()["code"] == "document_not_found"


async def _request(
    app: FastAPI,
    method: str,
    path: str,
    token: str,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.request(
            method,
            path,
            headers={"Authorization": f"Bearer {token}"},
        )
