import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paysentineliq.domain.document import Document, DocumentKind
from paysentineliq.infrastructure.db.models import DocumentModel, UserModel
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork

pytestmark = [pytest.mark.integration, pytest.mark.docker]


async def test_document_repository_filters_by_owner() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    owner_ids = []

    try:
        async with factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            async with uow:
                owner = await uow.users.create(
                    google_sub=f"owner-{unique}",
                    email=f"owner-{unique}@example.com",
                    name="Owner",
                )
                other = await uow.users.create(
                    google_sub=f"other-{unique}",
                    email=f"other-{unique}@example.com",
                    name="Other",
                )
                owner_ids = [owner.id, other.id]

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
                await uow.commit()

                found = await uow.documents.get_by_id_for_owner(
                    stored.id,
                    owner.id,
                )
                denied = await uow.documents.get_by_id_for_owner(
                    stored.id,
                    other.id,
                )

                assert found == stored
                assert denied is None
    finally:
        async with factory() as session:
            await session.execute(
                delete(DocumentModel).where(DocumentModel.owner_id.in_(owner_ids))
            )
            await session.execute(delete(UserModel).where(UserModel.id.in_(owner_ids)))
            await session.commit()
        await engine.dispose()
