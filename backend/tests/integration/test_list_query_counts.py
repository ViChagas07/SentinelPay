import os
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisRecord,
    AnalysisStatus,
)
from paysentineliq.domain.document import Document, DocumentKind
from paysentineliq.domain.user import User
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.db.models import (
    AnalysisEventModel,
    AnalysisModel,
    DocumentModel,
    NotificationModel,
    PayableModel,
    UserModel,
)
from paysentineliq.infrastructure.db.repositories.analyses import SqlAlchemyAnalysisRepository
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService
from paysentineliq.interface.api.main import create_app
from tests.support.query_counter import count_queries

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class FakeRevokedStore:
    async def revoke(self, jti: str, expires_at: int) -> None:
        return None

    async def is_revoked(self, jti: str) -> bool:
        return False


def _document(owner_id: UUID, index: int) -> Document:
    unique = uuid4()
    return Document(
        id=uuid4(),
        owner_id=owner_id,
        kind=DocumentKind.BANK_SLIP,
        s3_key=f"users/{owner_id}/bank_slip/{unique}/original.pdf",
        sha256=unique.hex * 2,
        size=64,
        content_type="application/pdf",
        original_name_sanitized=f"doc-{index}.pdf",
        created_at=_NOW,
    )


async def _seed(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[User, list[UUID], list[UUID]]:
    async with factory() as session:
        uow = SqlAlchemyUnitOfWork(session)
        async with uow:
            owner = await uow.users.create(
                google_sub=f"query-owner-{uuid4().hex}",
                email=f"query-owner-{uuid4().hex}@example.com",
                name="Query Owner",
            )
            documents = [await uow.documents.add(_document(owner.id, index)) for index in range(3)]
            await uow.commit()

    analyses: list[UUID] = []
    analysis_repository = SqlAlchemyAnalysisRepository(factory)
    for index, document in enumerate(documents):
        analysis_id = uuid4()
        await analysis_repository.create(
            AnalysisRecord(
                id=analysis_id,
                owner_id=owner.id,
                document_id=document.id,
                document_type=AnalysisDocumentType.BOLETO,
                status=AnalysisStatus.QUEUED,
                score=None,
                band=None,
                rule_set_version=None,
                model_versions={},
                degradation_flags=(),
                state={},
                report_s3_key=None,
                error_code=None,
                created_at=_NOW - timedelta(minutes=index),
                updated_at=_NOW - timedelta(minutes=index),
            ),
        )
        analyses.append(analysis_id)

    async with factory() as session, session.begin():
        for index, analysis_id in enumerate(analyses):
            session.add(
                PayableModel(
                    owner_id=owner.id,
                    analysis_id=analysis_id,
                    description=f"Conta sintetica {index}",
                    amount_cents=10_000 + index,
                    due_date=date(2026, 1, 10 + index),
                    status="pending",
                    created_at=_NOW,
                    updated_at=_NOW,
                ),
            )
            session.add(
                NotificationModel(
                    owner_id=owner.id,
                    analysis_id=analysis_id,
                    type="analysis_completed",
                    payload={"analysis_id": str(analysis_id)},
                    status="pending",
                    channel="in_app",
                    created_at=_NOW + timedelta(minutes=index),
                    updated_at=_NOW + timedelta(minutes=index),
                ),
            )
    return owner, analyses, [document.id for document in documents]


async def _cleanup(
    factory: async_sessionmaker[AsyncSession],
    owner_ids: list[UUID],
    analyses: list[UUID],
    documents: list[UUID],
) -> None:
    async with factory() as session:
        if owner_ids:
            await session.execute(
                delete(NotificationModel).where(NotificationModel.owner_id.in_(owner_ids)),
            )
            await session.execute(
                delete(PayableModel).where(PayableModel.owner_id.in_(owner_ids)),
            )
        if analyses:
            await session.execute(
                delete(AnalysisEventModel).where(AnalysisEventModel.analysis_id.in_(analyses)),
            )
            await session.execute(delete(AnalysisModel).where(AnalysisModel.id.in_(analyses)))
        if documents:
            await session.execute(delete(DocumentModel).where(DocumentModel.id.in_(documents)))
        if owner_ids:
            await session.execute(delete(UserModel).where(UserModel.id.in_(owner_ids)))
        await session.commit()


async def _get(app: FastAPI, path: str, headers: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=headers)


async def test_listing_endpoints_keep_query_count_constant() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    owner_ids: list[UUID] = []
    analyses: list[UUID] = []
    documents: list[UUID] = []
    try:
        owner, analyses, documents = await _seed(factory)
        owner_ids = [owner.id]

        settings = Settings(
            app_env="local",
            jwt_secret="q" * 64,
            security_hash_secret="h" * 32,
        )
        app = create_app(settings)
        token_service = JwtAccessTokenService(secret=settings.jwt_secret, ttl_minutes=15)
        app.state.session_factory = factory
        app.state.token_service = token_service
        app.state.revoked_tokens = FakeRevokedStore()
        token = token_service.issue(owner).token
        headers = {"Authorization": f"Bearer {token}"}

        paths = (
            "/api/v1/analyses",
            "/api/v1/payables",
            "/api/v1/notifications",
        )
        for path in paths:
            for limit in (1, 3):
                with count_queries(engine) as counter:
                    response = await _get(app, f"{path}?limit={limit}", headers)
                assert response.status_code == 200, response.text
                assert len(response.json()["items"]) == limit
                assert counter.select_count == 2, (
                    f"{path} com limit={limit} fez {counter.select_count} SELECTs; "
                    "esperado 1 de auth + 1 da lista"
                )
    finally:
        await _cleanup(factory, owner_ids, analyses, documents)
        await engine.dispose()
