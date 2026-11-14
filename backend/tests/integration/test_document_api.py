import io
import os
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import boto3
import httpx
import pytest
from botocore.config import Config
from pypdf import PdfWriter
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paysentineliq.infrastructure.db.models import DocumentModel, UserModel
from paysentineliq.infrastructure.db.uow import SqlAlchemyUnitOfWork
from paysentineliq.infrastructure.security.jwt import JwtAccessTokenService

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BUCKET = "paysentineliq-documents"
_ENDPOINT = "http://localhost:9000"


def _jwt_secret() -> str:
    for line in (_REPO_ROOT / ".env.example").read_text().splitlines():
        if line.startswith("JWT_SECRET="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("JWT_SECRET not found in .env.example")


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _s3_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="CHANGE_ME",
        aws_secret_access_key="CHANGE_ME",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


async def test_upload_api_writes_owner_prefix_and_blocks_idor() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4().hex
    owner_id = None
    other_id = None
    document_id: UUID | None = None
    object_key: str | None = None
    s3 = _s3_client()

    try:
        async with factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            async with uow:
                owner = await uow.users.create(
                    google_sub=f"api-owner-{unique}",
                    email=f"api-owner-{unique}@example.com",
                    name="API Owner",
                )
                other = await uow.users.create(
                    google_sub=f"api-other-{unique}",
                    email=f"api-other-{unique}@example.com",
                    name="API Other",
                )
                owner_id = owner.id
                other_id = other.id
                await uow.commit()

        token_service = JwtAccessTokenService(
            secret=_jwt_secret(),
            ttl_minutes=15,
        )
        owner_token = token_service.issue(owner).token
        other_token = token_service.issue(other).token
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        other_headers = {"Authorization": f"Bearer {other_token}"}

        async with httpx.AsyncClient(
            base_url="http://localhost:8000",
            timeout=20.0,
        ) as client:
            upload = await client.post(
                "/api/v1/documents/upload",
                headers=owner_headers,
                data={"kind": "bank_slip"},
                files={
                    "file": (
                        "../../boleto.pdf",
                        _pdf_bytes(),
                        "application/pdf",
                    )
                },
            )
            assert upload.status_code == 201, upload.text
            body = upload.json()
            document_id = UUID(body["id"])
            analysis_id = UUID(body["analysis_id"])
            assert body["original_name_sanitized"] == "boleto.pdf"

            owner_url = await client.get(
                f"/api/v1/documents/{document_id}/url",
                headers=owner_headers,
            )
            assert owner_url.status_code == 200
            assert "X-Amz-Expires=300" in owner_url.json()["url"]

            denied_url = await client.get(
                f"/api/v1/documents/{document_id}/url",
                headers=other_headers,
            )
            assert denied_url.status_code == 404
            assert denied_url.json()["code"] == "document_not_found"

        async with factory() as session:
            stored = await session.get(DocumentModel, document_id)
            assert stored is not None
            object_key = stored.s3_key
            assert object_key == (f"users/{owner_id}/bank_slip/{analysis_id}/original.pdf")

        head = s3.head_object(Bucket=_BUCKET, Key=object_key)
        assert head.get("ServerSideEncryption") == "AES256"
        assert head["Metadata"]["original_name"] == "boleto.pdf"
    finally:
        if object_key is not None:
            s3.delete_object(Bucket=_BUCKET, Key=object_key)
        async with factory() as session:
            if document_id is not None:
                await session.execute(delete(DocumentModel).where(DocumentModel.id == document_id))
            owner_ids = [value for value in (owner_id, other_id) if value]
            if owner_ids:
                await session.execute(delete(UserModel).where(UserModel.id.in_(owner_ids)))
            await session.commit()
        await engine.dispose()
