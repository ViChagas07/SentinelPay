from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from paysentineliq.application.commands.documents import (
    UploadDocumentCommand,
    UploadedDocumentResult,
)
from paysentineliq.application.errors import (
    DangerousPdfError,
    DocumentNotFoundError,
    UnsupportedDocumentTypeError,
    UploadTooLargeError,
)
from paysentineliq.application.queries.documents import (
    DocumentDownloadUrlDTO,
    GetDocumentDownloadUrlQuery,
)
from paysentineliq.domain.document import Document, DocumentKind
from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService
from paysentineliq.interface.api.dependencies import (
    get_auth_unit_of_work,
    get_document_download_query,
    get_upload_document_handler,
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


class FakeUploadHandler:
    def __init__(self) -> None:
        self.upload_error: Exception | None = None
        self.result: UploadedDocumentResult | None = None

    async def handle(self, command: UploadDocumentCommand) -> UploadedDocumentResult:
        if self.upload_error is not None:
            raise self.upload_error
        self.result = UploadedDocumentResult(
            document_id=_DOCUMENT.id,
            analysis_id=uuid4(),
            kind=command.kind,
            sha256=_DOCUMENT.sha256,
            size=_DOCUMENT.size,
            content_type=_DOCUMENT.content_type,
            original_name_sanitized="boleto.pdf",
            created_at=_NOW,
        )
        return self.result


class FakeDownloadHandler:
    def __init__(self) -> None:
        self.download_error: Exception | None = None
        self.url = "https://storage.example/short-url"

    async def handle(
        self,
        query: GetDocumentDownloadUrlQuery,
    ) -> DocumentDownloadUrlDTO:
        if self.download_error is not None:
            raise self.download_error
        return DocumentDownloadUrlDTO(url=self.url, expires_in=60)


def _app(
    upload_handler: FakeUploadHandler | None = None,
    download_handler: FakeDownloadHandler | None = None,
) -> tuple[FastAPI, str, FakeUploadHandler, FakeDownloadHandler]:
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
    fake_upload = upload_handler or FakeUploadHandler()
    fake_download = download_handler or FakeDownloadHandler()
    app.dependency_overrides[get_auth_unit_of_work] = FakeAuthUow
    app.dependency_overrides[get_upload_document_handler] = lambda: fake_upload
    app.dependency_overrides[get_document_download_query] = lambda: fake_download
    token = token_service.issue(_USER).token
    return app, token, fake_upload, fake_download


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
    app, _, _, _ = _app()

    response = await _upload(app, None)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


async def test_valid_upload_returns_created_document() -> None:
    app, token, upload, _ = _app()

    response = await _upload(
        app,
        token,
        filename="../../etc/boleto.pdf",
    )

    assert response.status_code == 201
    assert upload.result is not None
    body = response.json()
    assert body["kind"] == "bank_slip"
    assert body["analysis_id"] == str(upload.result.analysis_id)
    assert body["original_name_sanitized"] == "boleto.pdf"


async def test_upload_too_large_returns_problem_json() -> None:
    app, token, upload, _ = _app()
    upload.upload_error = UploadTooLargeError()

    response = await _upload(app, token)

    assert response.status_code == 413
    assert response.json()["code"] == "upload_too_large"


async def test_unsupported_document_returns_problem_json() -> None:
    app, token, upload, _ = _app()
    upload.upload_error = UnsupportedDocumentTypeError()

    response = await _upload(app, token, data=b"not a document")

    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_document_type"


async def test_dangerous_pdf_returns_evidence() -> None:
    app, token, upload, _ = _app()
    upload.upload_error = DangerousPdfError(("javascript",))

    response = await _upload(app, token)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "pdf_active_content"
    assert body["evidence"] == ["javascript"]


async def test_download_url_is_short_and_scoped() -> None:
    app, token, _, _ = _app()

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
    app, token, _, download = _app()
    download.download_error = DocumentNotFoundError()

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
