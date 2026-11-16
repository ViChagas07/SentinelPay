import asyncio
import os
from dataclasses import replace
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from paysentineliq.domain.user import Role, User
from paysentineliq.infrastructure.db.models import (
    AnalysisEventModel,
    AnalysisModel,
    DocumentModel,
    NotificationModel,
    PayableModel,
    ReminderPreferenceModel,
    UserModel,
)
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
_JWT_SECRET = os.environ.get("JWT_SECRET", "CHANGE_ME_USE_AT_LEAST_32_RANDOM_BYTES")
_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _auth(user: User) -> dict[str, str]:
    token = JwtAccessTokenService(secret=_JWT_SECRET, ttl_minutes=15).issue(user)
    return {"Authorization": f"Bearer {token.token}"}


async def _create_users(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[User, User]:
    async with factory() as session:
        uow = SqlAlchemyUnitOfWork(session)
        async with uow:
            owner = await uow.users.create(
                google_sub=f"security-owner-{uuid4().hex}",
                email=f"security-owner-{uuid4().hex}@example.com",
                name="Security Owner",
            )
            other = await uow.users.create(
                google_sub=f"security-other-{uuid4().hex}",
                email=f"security-other-{uuid4().hex}@example.com",
                name="Security Other",
            )
            await uow.commit()
    return owner, other


async def _seed_resources(
    factory: async_sessionmaker[AsyncSession],
    *,
    owner_id: UUID,
) -> tuple[UUID, UUID, UUID, UUID]:
    unique = uuid4()
    document_id = uuid4()
    analysis_id = uuid4()
    payable_id = uuid4()
    notification_id = uuid4()
    async with factory() as session, session.begin():
        session.add(
            DocumentModel(
                id=document_id,
                owner_id=owner_id,
                kind="bank_slip",
                s3_key=f"users/{owner_id}/bank_slip/{unique}/original.pdf",
                sha256=unique.hex * 2,
                size=64,
                content_type="application/pdf",
                original_name_sanitized="boleto.pdf",
                created_at=_NOW,
                updated_at=_NOW,
            ),
        )
        await session.flush()
        session.add(
            AnalysisModel(
                id=analysis_id,
                owner_id=owner_id,
                document_id=document_id,
                document_type="boleto",
                status="queued",
                score=None,
                band=None,
                rule_set_version=None,
                model_versions={},
                degradation_flags=[],
                state={},
                report_s3_key=None,
                error_code=None,
                created_at=_NOW,
                updated_at=_NOW,
            ),
        )
        await session.flush()
        session.add(
            PayableModel(
                id=payable_id,
                owner_id=owner_id,
                analysis_id=analysis_id,
                description="Conta sintetica",
                amount_cents=18_475,
                due_date=date(2026, 2, 10),
                status="pending_confirmation",
                created_at=_NOW,
                updated_at=_NOW,
            ),
        )
        session.add(
            NotificationModel(
                id=notification_id,
                owner_id=owner_id,
                analysis_id=analysis_id,
                type="analysis_completed",
                payload={"analysis_id": str(analysis_id)},
                status="pending",
                channel="in_app",
                created_at=_NOW,
                updated_at=_NOW,
            ),
        )
    return document_id, analysis_id, payable_id, notification_id


async def _request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    headers: dict[str, str],
    json: dict[str, object] | None = None,
) -> httpx.Response:
    for _ in range(4):
        response = await client.request(method, path, headers=headers, json=json)
        if response.status_code != 429:
            return response
        await asyncio.sleep(min(float(response.headers.get("Retry-After", "1")), 2.0))
    return response


async def _cleanup(
    factory: async_sessionmaker[AsyncSession],
    user_ids: list[UUID],
) -> None:
    async with factory() as session:
        if user_ids:
            await session.execute(
                delete(NotificationModel).where(NotificationModel.owner_id.in_(user_ids)),
            )
            await session.execute(
                delete(PayableModel).where(PayableModel.owner_id.in_(user_ids)),
            )
            await session.execute(
                delete(ReminderPreferenceModel).where(
                    ReminderPreferenceModel.user_id.in_(user_ids),
                ),
            )
            analysis_ids = select(AnalysisModel.id).where(AnalysisModel.owner_id.in_(user_ids))
            await session.execute(
                delete(AnalysisEventModel).where(
                    AnalysisEventModel.analysis_id.in_(analysis_ids),
                ),
            )
            await session.execute(
                delete(AnalysisModel).where(AnalysisModel.owner_id.in_(user_ids)),
            )
            await session.execute(
                delete(DocumentModel).where(DocumentModel.owner_id.in_(user_ids)),
            )
            await session.execute(delete(UserModel).where(UserModel.id.in_(user_ids)))
        await session.commit()


async def test_owner_routes_block_idor_and_role_escalation() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    user_ids: list[UUID] = []
    try:
        owner, other = await _create_users(factory)
        user_ids = [owner.id, other.id]
        document_id, analysis_id, payable_id, notification_id = await _seed_resources(
            factory,
            owner_id=owner.id,
        )
        owner_headers = _auth(owner)
        other_headers = _auth(other)

        async with httpx.AsyncClient(base_url=_API_URL, timeout=20) as client:
            owner_detail = await _request(
                client,
                "GET",
                f"/api/v1/analyses/{analysis_id}",
                headers=owner_headers,
            )
            assert owner_detail.status_code == 200, owner_detail.text
            assert owner_detail.json()["status"] == "queued"

            foreign_detail = await _request(
                client,
                "GET",
                f"/api/v1/analyses/{analysis_id}",
                headers=other_headers,
            )
            assert foreign_detail.status_code == 404
            assert foreign_detail.json()["code"] == "analysis_not_found"

            owner_url = await _request(
                client,
                "GET",
                f"/api/v1/documents/{document_id}/url",
                headers=owner_headers,
            )
            assert owner_url.status_code == 200, owner_url.text
            foreign_url = await _request(
                client,
                "GET",
                f"/api/v1/documents/{document_id}/url",
                headers=other_headers,
            )
            assert foreign_url.status_code == 404
            assert foreign_url.json()["code"] == "document_not_found"

            for action in ("confirm", "pay", "dismiss"):
                response = await _request(
                    client,
                    "POST",
                    f"/api/v1/payables/{payable_id}/{action}",
                    headers=other_headers,
                )
                assert response.status_code == 404, response.text
                assert response.json()["code"] == "payable_not_found"

            reschedule = await _request(
                client,
                "PATCH",
                f"/api/v1/payables/{payable_id}/due-date",
                headers=other_headers,
                json={"due_date": "2026-03-01"},
            )
            assert reschedule.status_code == 404
            assert reschedule.json()["code"] == "payable_not_found"

            foreign_read = await _request(
                client,
                "POST",
                f"/api/v1/notifications/{notification_id}/read",
                headers=other_headers,
            )
            assert foreign_read.status_code == 404
            assert foreign_read.json()["code"] == "notification_not_found"

            foreign_delete = await _request(
                client,
                "DELETE",
                f"/api/v1/notifications/{notification_id}",
                headers=other_headers,
            )
            assert foreign_delete.status_code == 404
            assert foreign_delete.json()["code"] == "notification_not_found"

            for path, resource_id in (
                ("/api/v1/analyses", analysis_id),
                ("/api/v1/payables", payable_id),
                ("/api/v1/notifications", notification_id),
            ):
                listing = await _request(client, "GET", path, headers=other_headers)
                assert listing.status_code == 200, listing.text
                assert all(item["id"] != str(resource_id) for item in listing.json()["items"])

            owner_payables = await _request(
                client,
                "GET",
                "/api/v1/payables",
                headers=owner_headers,
            )
            assert owner_payables.status_code == 200
            assert any(item["id"] == str(payable_id) for item in owner_payables.json()["items"])

            other_preferences = await _request(
                client,
                "PUT",
                "/api/v1/payables/reminder-preferences",
                headers=other_headers,
                json={"offsets_days": [7], "local_time": "18:30:00", "channels": ["in_app"]},
            )
            assert other_preferences.status_code == 200, other_preferences.text
            owner_preferences = await _request(
                client,
                "GET",
                "/api/v1/payables/reminder-preferences",
                headers=owner_headers,
            )
            assert owner_preferences.status_code == 200
            assert owner_preferences.json()["offsets_days"] == [3, 1, 0]

            user_admin = await _request(
                client,
                "GET",
                "/api/v1/protected/admin",
                headers=other_headers,
            )
            assert user_admin.status_code == 403

            claimed_admin = _auth(replace(other, role=Role.ADMIN))
            escalated = await _request(
                client,
                "GET",
                "/api/v1/protected/admin",
                headers=claimed_admin,
            )
            assert escalated.status_code == 403, escalated.text

        async with factory() as session, session.begin():
            await session.execute(
                update(UserModel).where(UserModel.id == other.id).values(role="admin"),
            )

        async with httpx.AsyncClient(base_url=_API_URL, timeout=20) as client:
            promoted = await _request(
                client,
                "GET",
                "/api/v1/protected/admin",
                headers=claimed_admin,
            )
            assert promoted.status_code == 200, promoted.text
            assert promoted.json()["role"] == "admin"

        async with factory() as session:
            payable = await session.get(PayableModel, payable_id)
            notification = await session.get(NotificationModel, notification_id)
        assert payable is not None
        assert payable.status == "pending_confirmation"
        assert payable.due_date == date(2026, 2, 10)
        assert notification is not None
        assert notification.read_at is None
    finally:
        await _cleanup(factory, user_ids)
        await engine.dispose()
