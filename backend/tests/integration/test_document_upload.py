import io
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pypdf import PdfWriter
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paysentineliq.application.use_cases.documents import DocumentService
from paysentineliq.domain.document import DocumentKind
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.db.models import DocumentModel, UserModel
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork
from paysentineliq.infrastructure.storage.inspector import (
    PdfImageDocumentInspector,
)
from paysentineliq.infrastructure.storage.s3 import S3StorageAdapter

pytestmark = [pytest.mark.integration, pytest.mark.docker]


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


async def test_upload_writes_owner_prefix_to_minio_and_database() -> None:
    settings = Settings(
        app_env="local",
        s3_endpoint_url="http://localhost:9000",
        s3_region="us-east-1",
        s3_bucket="paysentineliq-documents",
        s3_access_key_id="CHANGE_ME",
        s3_secret_access_key="CHANGE_ME",
        upload_max_mb=1,
        pdf_max_pages=5,
    )
    storage = S3StorageAdapter(
        settings,
        create_bucket_if_missing=True,
    )
    await storage.ensure_bucket()

    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    key = None
    user_id = None

    try:
        async with factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            async with uow:
                user = await uow.users.create(
                    google_sub=f"upload-{unique}",
                    email=f"upload-{unique}@example.com",
                    name="Upload User",
                )
                user_id = user.id
                await uow.commit()

            service = DocumentService(
                uow,
                storage,
                PdfImageDocumentInspector(),
                max_bytes=1024 * 1024,
                max_pdf_pages=5,
                presigned_ttl_seconds=60,
                clock=lambda: datetime.now(UTC),
            )
            uploaded = await service.upload(
                owner_id=user.id,
                kind=DocumentKind.BANK_SLIP,
                original_name="../../boleto.pdf",
                stream=io.BytesIO(_pdf_bytes()),
            )
            key = uploaded.document.s3_key

            assert key.startswith(f"users/{user.id}/bank_slip/{uploaded.analysis_id}/")
            assert key.endswith("/original.pdf")
            assert uploaded.document.original_name_sanitized == "boleto.pdf"

            found = await uow.documents.get_by_id_for_owner(
                uploaded.document.id,
                user.id,
            )
            assert found is not None
            assert found.sha256 == uploaded.document.sha256

        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url="http://localhost:9000",
            region_name="us-east-1",
            aws_access_key_id="CHANGE_ME",
            aws_secret_access_key="CHANGE_ME",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )
        head = client.head_object(
            Bucket="paysentineliq-documents",
            Key=key,
        )
        assert head.get("ServerSideEncryption") == "AES256"
        assert head["Metadata"]["original_name"] == "boleto.pdf"
    finally:
        if key is not None:
            await storage.delete(key)
        async with factory() as session:
            if user_id is not None:
                await session.execute(
                    delete(DocumentModel).where(DocumentModel.owner_id == user_id)
                )
                await session.execute(delete(UserModel).where(UserModel.id == user_id))
                await session.commit()
        await engine.dispose()
