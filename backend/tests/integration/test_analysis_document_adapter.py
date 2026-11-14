import os
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paysentineliq.domain.document import Document, DocumentKind
from paysentineliq.infrastructure.db.models import DocumentModel, UserModel
from paysentineliq.infrastructure.db.repositories.analysis_documents import (
    SqlAlchemyAnalysisDocumentAdapter,
)
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork

pytestmark = [pytest.mark.integration, pytest.mark.docker]


class FakeStorage:
    def __init__(self, chunks: tuple[bytes, ...]) -> None:
        self._chunks = chunks

    async def put(
        self,
        key: str,
        stream: BinaryIO,
        *,
        content_type: str,
        size: int,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        return None

    async def get_stream(self, key: str) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk

    async def delete(self, key: str) -> None:
        return None

    async def presigned_get_url(self, key: str, *, expires_in: int) -> str:
        return f"https://storage.example/{key}"


async def test_analysis_document_adapter_gets_metadata_and_streams_bytes() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    owner_id = None

    try:
        async with factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            async with uow:
                owner = await uow.users.create(
                    google_sub=f"adapter-{unique}",
                    email=f"adapter-{unique}@example.com",
                    name="Owner",
                )
                owner_id = owner.id
                document = Document(
                    id=uuid4(),
                    owner_id=owner.id,
                    kind=DocumentKind.PAYSLIP,
                    s3_key=f"users/{owner.id}/payslip/{uuid4()}/original.pdf",
                    sha256="a" * 64,
                    size=6,
                    content_type="application/pdf",
                    original_name_sanitized="payslip.pdf",
                    created_at=datetime.now(UTC),
                )
                stored = await uow.documents.add(document)
                await uow.commit()
        storage = FakeStorage((b"abc", b"def"))
        adapter = SqlAlchemyAnalysisDocumentAdapter(factory, storage)

        metadata = await adapter.get(stored.id)
        data = await adapter.read(metadata) if metadata is not None else b""

        assert metadata is not None
        assert metadata.owner_id == owner_id
        assert metadata.kind is DocumentKind.PAYSLIP
        assert data == b"abcdef"
        assert await adapter.get(uuid4()) is None
    finally:
        if owner_id is not None:
            async with factory() as session:
                await session.execute(
                    delete(DocumentModel).where(DocumentModel.owner_id == owner_id),
                )
                await session.execute(
                    delete(UserModel).where(UserModel.id == owner_id),
                )
                await session.commit()
        await engine.dispose()
