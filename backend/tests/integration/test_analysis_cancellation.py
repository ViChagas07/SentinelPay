import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from paysentineliq.application.ports.analysis_cancellation import CancelOutcome
from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisEvent,
    AnalysisEventType,
    AnalysisRecord,
    AnalysisStatus,
)
from paysentineliq.domain.document import Document, DocumentKind
from paysentineliq.domain.scoring import RiskBand
from paysentineliq.infrastructure.db.models import AnalysisModel
from paysentineliq.infrastructure.db.repositories.analyses import (
    SqlAlchemyAnalysisRepository,
)
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def _setup(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[SqlAlchemyAnalysisRepository, AnalysisRecord]:
    unique = uuid4().hex
    async with factory() as session:
        uow = SqlAlchemyUnitOfWork(session)
        async with uow:
            owner = await uow.users.create(
                google_sub=f"cancel-{unique}",
                email=f"cancel-{unique}@example.com",
                name="Owner",
            )
            document = Document(
                id=uuid4(),
                owner_id=owner.id,
                kind=DocumentKind.BANK_SLIP,
                s3_key=f"users/{owner.id}/bank_slip/{uuid4()}/original.pdf",
                sha256="b" * 64,
                size=123,
                content_type="application/pdf",
                original_name_sanitized="boleto.pdf",
                created_at=datetime.now(UTC),
            )
            stored = await uow.documents.add(document)
            await uow.commit()
    repository = SqlAlchemyAnalysisRepository(factory)
    record = AnalysisRecord(
        id=uuid4(),
        owner_id=owner.id,
        document_id=stored.id,
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
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await repository.create(record)
    return repository, record


async def _row(
    factory: async_sessionmaker[AsyncSession],
    analysis_id: object,
) -> AnalysisModel:
    async with factory() as session:
        model = await session.scalar(
            select(AnalysisModel).where(AnalysisModel.id == analysis_id),
        )
    assert model is not None
    return model


async def test_queued_cancel_is_immediate_and_clears_partial_result() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        repository, record = await _setup(factory)
        now = datetime.now(UTC)
        transition = await repository.request_cancel(
            record.id,
            record.owner_id,
            now=now,
            event=AnalysisEvent(
                analysis_id=record.id,
                event_type=AnalysisEventType.CANCELLED,
                payload={"reason": "test"},
            ),
        )

        row = await _row(factory, record.id)
        assert transition.outcome is CancelOutcome.CANCELLED
        assert row.status == "cancelled"
        assert row.cancelled_at is not None
        assert row.score is None
        assert row.report_s3_key is None
        assert row.state == {}
    finally:
        await engine.dispose()


async def test_cancel_before_complete_wins_the_race() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        repository, record = await _setup(factory)
        claimed = await repository.claim_for_processing(
            record.id,
            task_id="task-race",
            lease_seconds=300,
        )
        assert claimed is not None
        transition = await repository.request_cancel(
            record.id,
            record.owner_id,
            now=datetime.now(UTC),
            event=AnalysisEvent(
                analysis_id=record.id,
                event_type=AnalysisEventType.CANCELLING,
                payload={"stage": "cancel"},
            ),
        )
        assert transition.outcome is CancelOutcome.REQUESTED

        completed = await repository.complete(
            record.id,
            score=91,
            band=RiskBand.HIGH,
            rule_set_version="rules-v1",
            model_versions={"ml": "model-v1"},
            degradation_flags=(),
            state={"node": "persist"},
            report_s3_key="users/owner/analyses/id/report.json",
            event=None,
            notifications=(),
            payables=(),
        )
        finalized = await repository.finalize_cancelled(
            record.id,
            event=AnalysisEvent(
                analysis_id=record.id,
                event_type=AnalysisEventType.CANCELLED,
                payload={"reason": "test"},
            ),
        )

        row = await _row(factory, record.id)
        assert completed is False
        assert finalized is True
        assert row.status == "cancelled"
        assert row.score is None
        assert row.report_s3_key is None
    finally:
        await engine.dispose()


async def test_complete_before_cancel_wins_the_race() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        repository, record = await _setup(factory)
        assert (
            await repository.claim_for_processing(
                record.id,
                task_id="task-race-2",
                lease_seconds=300,
            )
            is not None
        )
        completed = await repository.complete(
            record.id,
            score=91,
            band=RiskBand.HIGH,
            rule_set_version="rules-v1",
            model_versions={"ml": "model-v1"},
            degradation_flags=(),
            state={"node": "persist"},
            report_s3_key="users/owner/analyses/id/report.json",
            event=None,
            notifications=(),
            payables=(),
        )
        transition = await repository.request_cancel(
            record.id,
            record.owner_id,
            now=datetime.now(UTC),
        )

        row = await _row(factory, record.id)
        assert completed is True
        assert transition.outcome is CancelOutcome.NOT_CANCELLABLE
        assert row.status == "completed"
        assert row.score == 91
    finally:
        await engine.dispose()
