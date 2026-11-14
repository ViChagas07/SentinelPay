import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisEvent,
    AnalysisEventType,
    AnalysisRecord,
    AnalysisStatus,
    DegradationFlag,
)
from paysentineliq.domain.document import Document, DocumentKind
from paysentineliq.domain.scoring import RiskBand
from paysentineliq.infrastructure.db.models import (
    AnalysisModel,
    DocumentModel,
    UserModel,
)
from paysentineliq.infrastructure.db.repositories.analyses import (
    SqlAlchemyAnalysisEventRepository,
    SqlAlchemyAnalysisRepository,
)
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_analysis_and_events_are_persisted_without_pii() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    owner_id = None
    document_id = None
    analysis_id = uuid4()

    try:
        async with factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            async with uow:
                owner = await uow.users.create(
                    google_sub=f"analysis-{unique}",
                    email=f"analysis-{unique}@example.com",
                    name="Owner",
                )
                owner_id = owner.id
                document = Document(
                    id=uuid4(),
                    owner_id=owner.id,
                    kind=DocumentKind.BANK_SLIP,
                    s3_key=f"users/{owner.id}/bank_slip/{uuid4()}/original.pdf",
                    sha256="a" * 64,
                    size=123,
                    content_type="application/pdf",
                    original_name_sanitized="boleto.pdf",
                    created_at=datetime.now(UTC),
                )
                stored = await uow.documents.add(document)
                document_id = stored.id
                await uow.commit()

        analyses = SqlAlchemyAnalysisRepository(factory)
        events = SqlAlchemyAnalysisEventRepository(factory)
        now = datetime.now(UTC)
        await analyses.create(
            AnalysisRecord(
                id=analysis_id,
                owner_id=owner_id,
                document_id=document_id,
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
                created_at=now,
                updated_at=now,
            ),
        )
        await events.append(
            AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.QUEUED,
                payload={"document_id": str(document_id)},
            ),
        )
        await analyses.update_state(
            analysis_id,
            status=AnalysisStatus.PROCESSING,
            state={"node": "fraud"},
            degradation_flags=(DegradationFlag.ML_UNAVAILABLE,),
        )
        await events.append(
            AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.RULE_TRIGGERED,
                rule_code="dv_invalid",
                rule_set_version="febraban-v1",
                model_version=None,
                payload={"weight": "70", "severity": "critical"},
            ),
        )
        await events.append(
            AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.DEGRADED,
                degradation_flags=(DegradationFlag.ML_UNAVAILABLE,),
                payload={"flag": "ml_unavailable"},
            ),
        )
        await events.append(
            AnalysisEvent(
                analysis_id=analysis_id,
                event_type=AnalysisEventType.COMPLETED,
                payload={"score": "80", "band": "high"},
            ),
        )
        await analyses.complete(
            analysis_id,
            score=80,
            band=RiskBand.HIGH,
            rule_set_version="febraban-v1",
            model_versions={"ml": "fraud-risk-v1"},
            degradation_flags=(DegradationFlag.ML_UNAVAILABLE,),
            state={"node": "persist", "score": "80"},
            report_s3_key=f"users/{owner_id}/analyses/{analysis_id}/report.json",
        )

        record = await analyses.get(analysis_id)
        assert record is not None
        assert record.status is AnalysisStatus.DEGRADED
        assert record.score == 80
        assert record.rule_set_version == "febraban-v1"
        assert record.report_s3_key is not None
        assert record.degradation_flags == (DegradationFlag.ML_UNAVAILABLE,)

        stored_events = await events.list_for_analysis(analysis_id)
        assert [event.event_type for event in stored_events] == [
            AnalysisEventType.QUEUED,
            AnalysisEventType.RULE_TRIGGERED,
            AnalysisEventType.DEGRADED,
            AnalysisEventType.COMPLETED,
        ]
        assert all(
            set(event.payload) <= {"document_id", "weight", "severity", "flag", "score", "band"}
            for event in stored_events
        )
        assert not hasattr(events, "update")
        assert not hasattr(events, "delete")

        failed_id = uuid4()
        await analyses.create(
            AnalysisRecord(
                id=failed_id,
                owner_id=owner_id,
                document_id=document_id,
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
                created_at=now,
                updated_at=now,
            ),
        )
        await analyses.fail(
            failed_id,
            error_code="ocr_failed",
            state={"node": "ingest"},
        )
        failed = await analyses.get(failed_id)
        assert failed is not None
        assert failed.status is AnalysisStatus.FAILED
        assert failed.error_code == "ocr_failed"
    finally:
        if owner_id is not None:
            async with factory() as session:
                await session.execute(
                    delete(AnalysisModel).where(AnalysisModel.owner_id == owner_id),
                )
                await session.execute(
                    delete(DocumentModel).where(DocumentModel.owner_id == owner_id),
                )
                await session.execute(
                    delete(UserModel).where(UserModel.id == owner_id),
                )
                await session.commit()
        await engine.dispose()
