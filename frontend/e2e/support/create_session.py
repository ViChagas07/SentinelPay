import asyncio
import json
import secrets
import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import update

from paysentineliq.application.commands.auth import AuthService, GoogleIdentity
from paysentineliq.infrastructure.config import get_settings
from paysentineliq.infrastructure.db.engine import build_engine, build_session_factory
from paysentineliq.infrastructure.db.models import (
    AnalysisModel,
    DocumentModel,
    NotificationModel,
    PayableModel,
    UserModel,
)
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService
from paysentineliq.infrastructure.security.revoked_tokens import RedisRevokedTokenStore
from redis.asyncio import Redis


def _document(user_id: UUID, kind: str) -> DocumentModel:
    return DocumentModel(
        id=uuid4(),
        owner_id=user_id,
        kind=kind,
        s3_key=f"e2e/dashboard/{uuid4()}.pdf",
        sha256=secrets.token_hex(32),
        size=1024,
        content_type="application/pdf",
        original_name_sanitized=f"e2e-{kind}.pdf",
    )


async def _analysis(
    session,
    user_id: UUID,
    kind: str,
    document_kind: str,
    status: str,
    score: int | None,
    band: str | None,
    created_at: datetime,
    error_code: str | None = None,
) -> AnalysisModel:
    document = _document(user_id, document_kind)
    session.add(document)
    await session.flush()
    analysis = AnalysisModel(
        id=uuid4(),
        owner_id=user_id,
        document_id=document.id,
        document_type=kind,
        status=status,
        score=score,
        band=band,
        rule_set_version="e2e-v1",
        model_versions={},
        degradation_flags=[],
        state={},
        error_code=error_code,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(analysis)
    return analysis


async def seed_dashboard(factory, user_id: UUID) -> dict:
    now = datetime.now(timezone.utc)
    today = now.date()

    async with factory() as session:
        await session.execute(
            update(UserModel).where(UserModel.id == user_id).values(timezone="UTC"),
        )

        a1 = await _analysis(
            session,
            user_id,
            "boleto",
            "bank_slip",
            "completed",
            12,
            "low",
            now - timedelta(days=1),
        )
        a2 = await _analysis(
            session,
            user_id,
            "boleto",
            "bank_slip",
            "completed",
            55,
            "attention",
            now - timedelta(days=3),
        )
        a3 = await _analysis(
            session,
            user_id,
            "payslip",
            "payslip",
            "completed",
            78,
            "high",
            now - timedelta(days=10),
        )
        a4 = await _analysis(
            session,
            user_id,
            "receipt",
            "receipt",
            "completed",
            32,
            "low",
            now - timedelta(days=20),
        )
        a5 = await _analysis(
            session,
            user_id,
            "boleto",
            "bank_slip",
            "processing",
            None,
            None,
            now - timedelta(hours=2),
        )
        a6 = await _analysis(
            session,
            user_id,
            "boleto",
            "bank_slip",
            "failed",
            None,
            None,
            now - timedelta(hours=1),
            error_code="processing_error",
        )
        a7 = await _analysis(
            session,
            user_id,
            "boleto",
            "bank_slip",
            "completed",
            60,
            "attention",
            now - timedelta(days=35),
        )
        a8 = await _analysis(
            session,
            user_id,
            "boleto",
            "bank_slip",
            "completed",
            70,
            "high",
            now - timedelta(days=40),
        )
        a9 = await _analysis(
            session,
            user_id,
            "boleto",
            "bank_slip",
            "completed",
            80,
            "high",
            now - timedelta(days=50),
        )
        await session.flush()

        payable_specs = [
            (a1, "Energia elétrica", 18475, today - timedelta(days=2), "overdue", -2),
            (a2, "Internet", 12990, today, "pending_confirmation", 0),
            (a3, "Aluguel", 250000, today + timedelta(days=3), "pending_confirmation", 3),
            (a4, "Água", 8950, today + timedelta(days=10), "pending", 10),
        ]
        payables = []

        for analysis, description, amount_cents, due_date, status, offset in payable_specs:
            payable = PayableModel(
                id=uuid4(),
                owner_id=user_id,
                analysis_id=analysis.id,
                description=description,
                amount_cents=amount_cents,
                due_date=due_date,
                status=status,
            )
            session.add(payable)
            payables.append(
                {
                    "id": str(payable.id),
                    "description": description,
                    "amount": f"{amount_cents / 100:.2f}",
                    "due_offset_days": offset,
                    "status": status,
                },
            )

        for index in range(2):
            created_at = now - timedelta(days=10 - index)
            session.add(
                NotificationModel(
                    id=uuid4(),
                    owner_id=user_id,
                    analysis_id=a3.id,
                    type="high_risk_detected",
                    payload={
                        "analysis_id": str(a3.id),
                        "score": "78",
                        "band": "high",
                    },
                    status="dispatched",
                    channel="in_app",
                    created_at=created_at,
                    updated_at=created_at,
                ),
            )

        await session.commit()

    current_scores = [12, 55, 78, 32]
    average = round(sum(current_scores) / len(current_scores))
    conformity = round(
        100 * sum(1 for score in current_scores if score < 40) / len(current_scores),
    )
    high_risk = sum(1 for score in current_scores if score >= 70)
    flagged = sum(1 for score in current_scores if score >= 40)

    return {
        "user_timezone": "UTC",
        "analysis_ids": {
            "failed": str(a6.id),
            "processing": str(a5.id),
            "completed": [str(a1.id), str(a2.id), str(a3.id), str(a4.id)],
            "previous": [str(a7.id), str(a8.id), str(a9.id)],
        },
        "payables": payables,
        "notifications": 2,
        "average": average,
        "conformity": conformity,
        "documents_analyzed": len(current_scores),
        "high_risk": high_risk,
        "flagged": flagged,
        "pending_receipts": 2,
        "seven_day_average": round((12 + 55) / 2),
        "seven_day_conformity": 50,
        "seven_day_documents": 2,
        "seven_day_high_risk": 0,
    }


async def main() -> None:
    settings = get_settings()
    engine = build_engine(settings)
    factory = build_session_factory(engine)
    session = factory()
    uow = SqlAlchemyUnitOfWork(session)
    tokens = JwtAccessTokenService(
        secret=settings.jwt_secret,
        ttl_minutes=settings.access_token_ttl_minutes,
    )
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    revoked = RedisRevokedTokenStore(redis)
    service = AuthService(
        uow,
        tokens,
        revoked,
        refresh_ttl_days=settings.refresh_token_ttl_days,
    )

    email = "e2e.session@paysentineliq.test"
    seed = False

    for argument in sys.argv[1:]:
        if argument == "--seed-dashboard":
            seed = True
        elif not argument.startswith("--"):
            email = argument

    result = await service.login_with_google(
        GoogleIdentity(
            google_sub=f"e2e-{secrets.token_hex(8)}",
            email=email,
            name="Sessão de teste",
        )
    )

    dashboard_seed = None

    if seed:
        dashboard_seed = await seed_dashboard(factory, UUID(str(result.user.id)))

    await session.close()
    await engine.dispose()
    await redis.aclose()

    payload = {
        "email": result.user.email,
        "access_token": result.access_token,
        "expires_in": result.expires_in_seconds,
        "refresh_token": result.refresh_token,
        "csrf_token": f"e2e-{secrets.token_urlsafe(24)}",
    }

    if dashboard_seed is not None:
        payload["seed"] = dashboard_seed

    print(json.dumps(payload))


asyncio.run(main())

