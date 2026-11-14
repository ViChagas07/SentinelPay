import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisEvent,
    AnalysisEventType,
    AnalysisRecord,
    AnalysisStatus,
)
from paysentineliq.domain.document import Document, DocumentKind
from paysentineliq.domain.notification import Notification, NotificationType
from paysentineliq.domain.scoring import RiskBand
from paysentineliq.infrastructure.db.models import (
    AnalysisModel,
    DocumentModel,
    UserModel,
)
from paysentineliq.infrastructure.db.repositories.analyses import (
    SqlAlchemyAnalysisRepository,
    SqlAlchemyNotificationRepository,
)
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_NOW = datetime.now(UTC)


def _record(
    analysis_id: UUID,
    owner_id: UUID,
    document_id: UUID,
    *,
    idempotency_key: str | None = None,
    status: AnalysisStatus = AnalysisStatus.QUEUED,
) -> AnalysisRecord:
    return AnalysisRecord(
        id=analysis_id,
        owner_id=owner_id,
        document_id=document_id,
        document_type=AnalysisDocumentType.BOLETO,
        status=status,
        score=None,
        band=None,
        rule_set_version=None,
        model_versions={},
        degradation_flags=(),
        state={},
        report_s3_key=None,
        error_code=None,
        created_at=_NOW,
        updated_at=_NOW,
        idempotency_key=idempotency_key,
        idempotency_request_hash="a" * 64 if idempotency_key else None,
    )


async def test_claim_is_idempotent_and_recovers_expired_lease() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    owner_id: UUID | None = None
    document_id: UUID | None = None
    analysis_id = uuid4()

    try:
        async with factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            async with uow:
                owner = await uow.users.create(
                    google_sub=f"queue-{unique}",
                    email=f"queue-{unique}@example.com",
                    name="Owner",
                )
                owner_id = owner.id
                document = await uow.documents.add(_document(owner.id))
                document_id = document.id
                await uow.commit()

        analyses = SqlAlchemyAnalysisRepository(factory)
        await analyses.create(
            _record(analysis_id, owner_id, document_id),
            event=AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.QUEUED,
            ),
        )

        first = await analyses.claim_for_processing(
            analysis_id,
            task_id="task-a",
            lease_seconds=300,
            event=AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.PROCESSING,
                payload={"task_id": "task-a"},
            ),
        )
        duplicate = await analyses.claim_for_processing(
            analysis_id,
            task_id="task-b",
            lease_seconds=300,
        )
        retry = await analyses.claim_for_processing(
            analysis_id,
            task_id="task-a",
            lease_seconds=300,
        )
        requeued = await analyses.requeue_for_retry(
            analysis_id,
            error_code="analysis_failed",
            state={"node": "retry"},
            event=AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.RETRY_SCHEDULED,
                payload={"error_code": "analysis_failed"},
            ),
        )
        reclaimed = await analyses.claim_for_processing(
            analysis_id,
            task_id="task-a",
            lease_seconds=300,
        )

        assert first is not None
        assert first.status is AnalysisStatus.PROCESSING
        assert duplicate is None
        assert retry is None
        assert requeued is True
        assert reclaimed is not None

        async with factory() as session:
            await session.execute(
                update(AnalysisModel)
                .where(AnalysisModel.id == analysis_id)
                .values(processing_started_at=_NOW - timedelta(seconds=600)),
            )
            await session.commit()

        recovered = await analyses.claim_for_processing(
            analysis_id,
            task_id="task-c",
            lease_seconds=300,
        )
        assert recovered is not None
        assert recovered.task_id == "task-c"
    finally:
        await _cleanup(factory, owner_id, analysis_id, document_id)
        await engine.dispose()


async def test_completion_is_terminal_and_records_event_and_notification_once() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    owner_id: UUID | None = None
    document_id: UUID | None = None
    analysis_id = uuid4()

    try:
        async with factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            async with uow:
                owner = await uow.users.create(
                    google_sub=f"complete-{unique}",
                    email=f"complete-{unique}@example.com",
                    name="Owner",
                )
                owner_id = owner.id
                document = await uow.documents.add(_document(owner.id))
                document_id = document.id
                await uow.commit()

        analyses = SqlAlchemyAnalysisRepository(factory)
        notifications = SqlAlchemyNotificationRepository(factory)
        await analyses.create(_record(analysis_id, owner_id, document_id))
        await analyses.claim_for_processing(
            analysis_id,
            task_id="task-a",
            lease_seconds=300,
        )
        notification = Notification(
            id=uuid4(),
            owner_id=owner_id,
            analysis_id=analysis_id,
            type=NotificationType.ANALYSIS_COMPLETED,
            payload={"analysis_id": str(analysis_id), "status": "completed"},
        )
        event = AnalysisEvent(
            analysis_id=analysis_id,
            event_type=AnalysisEventType.COMPLETED,
            payload={"score": "80", "band": "high"},
        )

        completed = await analyses.complete(
            analysis_id,
            score=80,
            band=RiskBand.HIGH,
            rule_set_version="febraban-v1",
            model_versions={"ml": "v1"},
            degradation_flags=(),
            state={"score": "80"},
            report_s3_key="reports/a.json",
            event=event,
            notifications=(notification,),
        )
        repeated = await analyses.complete(
            analysis_id,
            score=10,
            band=RiskBand.LOW,
            rule_set_version="febraban-v1",
            model_versions={},
            degradation_flags=(),
            state={},
            report_s3_key="reports/b.json",
            notifications=(notification,),
        )

        record = await analyses.get(analysis_id)
        pending = await notifications.list_pending_for_analysis(analysis_id)

        assert completed is True
        assert repeated is False
        assert record is not None
        assert record.status is AnalysisStatus.COMPLETED
        assert record.score == 80
        assert len(pending) == 1
        assert pending[0].payload["status"] == "completed"
    finally:
        await _cleanup(factory, owner_id, analysis_id, document_id)
        await engine.dispose()


async def test_failure_is_terminal_and_idempotency_is_unique() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    owner_id: UUID | None = None
    document_id: UUID | None = None
    analysis_id = uuid4()

    try:
        async with factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            async with uow:
                owner = await uow.users.create(
                    google_sub=f"fail-{unique}",
                    email=f"fail-{unique}@example.com",
                    name="Owner",
                )
                owner_id = owner.id
                document = await uow.documents.add(_document(owner.id))
                document_id = document.id
                await uow.commit()

        analyses = SqlAlchemyAnalysisRepository(factory)
        await analyses.create(
            _record(analysis_id, owner_id, document_id, idempotency_key="key-1"),
        )
        found = await analyses.find_by_idempotency(owner_id, "key-1")
        assert found is not None
        assert found.id == analysis_id

        failed = await analyses.fail(
            analysis_id,
            error_code="ocr_failed",
            state={"node": "ingest"},
            event=AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.FAILED,
                payload={"error_code": "ocr_failed"},
            ),
        )
        repeated = await analyses.fail(
            analysis_id,
            error_code="other",
            state={},
        )
        record = await analyses.get(analysis_id)

        assert failed is True
        assert repeated is False
        assert record is not None
        assert record.status is AnalysisStatus.FAILED
        assert record.error_code == "ocr_failed"

        active = await analyses.count_active_for_owner(owner_id)
        assert active == 0
    finally:
        await _cleanup(factory, owner_id, analysis_id, document_id)
        await engine.dispose()


async def test_stale_processor_is_listed() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    owner_id: UUID | None = None
    document_id: UUID | None = None
    analysis_id = uuid4()

    try:
        async with factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            async with uow:
                owner = await uow.users.create(
                    google_sub=f"stale-{unique}",
                    email=f"stale-{unique}@example.com",
                    name="Owner",
                )
                owner_id = owner.id
                document = await uow.documents.add(_document(owner.id))
                document_id = document.id
                await uow.commit()

        analyses = SqlAlchemyAnalysisRepository(factory)
        await analyses.create(_record(analysis_id, owner_id, document_id))
        await analyses.claim_for_processing(
            analysis_id,
            task_id="task-a",
            lease_seconds=300,
        )

        stale = await analyses.list_stale_processing(
            datetime.now(UTC) + timedelta(seconds=1),
        )

        assert [item.id for item in stale] == [analysis_id]
    finally:
        await _cleanup(factory, owner_id, analysis_id, document_id)
        await engine.dispose()


def _document(owner_id: UUID) -> Document:
    return Document(
        id=uuid4(),
        owner_id=owner_id,
        kind=DocumentKind.BANK_SLIP,
        s3_key=f"users/{owner_id}/bank_slip/{uuid4()}/original.pdf",
        sha256="a" * 64,
        size=123,
        content_type="application/pdf",
        original_name_sanitized="boleto.pdf",
        created_at=_NOW,
    )


async def _cleanup(
    factory: async_sessionmaker[AsyncSession],
    owner_id: UUID | None,
    analysis_id: UUID,
    document_id: UUID | None,
) -> None:
    if owner_id is None:
        return
    async with factory() as session:
        await session.execute(delete(AnalysisModel).where(AnalysisModel.id == analysis_id))
        if document_id is not None:
            await session.execute(delete(DocumentModel).where(DocumentModel.id == document_id))
        await session.execute(delete(UserModel).where(UserModel.id == owner_id))
        await session.commit()
