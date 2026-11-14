import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paysentineliq.domain.analysis import (
    AnalysisDocumentType,
    AnalysisRecord,
    AnalysisStatus,
)
from paysentineliq.domain.document import Document, DocumentKind
from paysentineliq.infrastructure.db.models import AnalysisModel, DocumentModel, UserModel
from paysentineliq.infrastructure.db.repositories.analyses import SqlAlchemyAnalysisRepository
from paysentineliq.infrastructure.db.repositories.analysis_read import (
    SqlAlchemyAnalysisReadRepository,
)
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_NOW = datetime.now(UTC)


def _record(
    analysis_id: UUID,
    owner_id: UUID,
    document_id: UUID,
    *,
    created_at: datetime,
) -> AnalysisRecord:
    return AnalysisRecord(
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
        created_at=created_at,
        updated_at=created_at,
    )


def _document(owner_id: UUID) -> Document:
    unique = uuid4()
    return Document(
        id=uuid4(),
        owner_id=owner_id,
        kind=DocumentKind.BANK_SLIP,
        s3_key=f"users/{owner_id}/bank_slip/{unique}/original.pdf",
        sha256=unique.hex * 2,
        size=123,
        content_type="application/pdf",
        original_name_sanitized="boleto.pdf",
        created_at=_NOW,
    )


async def test_list_is_owner_scoped_ordered_and_single_query() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    owners: list[UUID] = []
    analyses: list[UUID] = []
    documents: list[UUID] = []

    try:
        async with factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            async with uow:
                owner_a = await uow.users.create(
                    google_sub=f"read-a-{unique}",
                    email=f"read-a-{unique}@example.com",
                    name="Owner A",
                )
                owner_b = await uow.users.create(
                    google_sub=f"read-b-{unique}",
                    email=f"read-b-{unique}@example.com",
                    name="Owner B",
                )
                owners = [owner_a.id, owner_b.id]
                for owner in (owner_a, owner_b):
                    document = await uow.documents.add(_document(owner.id))
                    documents.append(document.id)
                await uow.commit()

        repository = SqlAlchemyAnalysisRepository(factory)
        created: list[UUID] = []
        for index in range(3):
            analysis_id = uuid4()
            await repository.create(
                _record(
                    analysis_id,
                    owners[0],
                    documents[0],
                    created_at=_NOW - timedelta(minutes=index),
                ),
            )
            created.append(analysis_id)
        other_id = uuid4()
        await repository.create(
            _record(other_id, owners[1], documents[1], created_at=_NOW),
        )
        analyses.extend(created)
        analyses.append(other_id)

        reader = SqlAlchemyAnalysisReadRepository(factory)
        statements: list[str] = []

        def count_selects(
            conn: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,
        ) -> None:
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", count_selects)
        try:
            page = await reader.list_for_owner(owners[0], limit=2)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", count_selects)

        assert [item.id for item in page] == created[:2]
        assert all(item.owner_id == owners[0] for item in page)
        assert len(statements) == 1

        cursor = (page[-1].created_at, page[-1].id)
        next_page = await reader.list_for_owner(owners[0], limit=2, before=cursor)
        assert [item.id for item in next_page] == created[2:]

        missing = await reader.get_for_owner(created[0], owners[1])
        assert missing is None
    finally:
        async with factory() as session:
            if analyses:
                await session.execute(
                    delete(AnalysisModel).where(AnalysisModel.id.in_(analyses)),
                )
            if documents:
                await session.execute(
                    delete(DocumentModel).where(DocumentModel.id.in_(documents)),
                )
            if owners:
                await session.execute(delete(UserModel).where(UserModel.id.in_(owners)))
            await session.commit()
        await engine.dispose()
