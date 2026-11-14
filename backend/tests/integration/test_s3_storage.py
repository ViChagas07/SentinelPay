import io
from typing import Any
from uuid import uuid4

import boto3
import httpx
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError

from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.storage.s3 import S3StorageAdapter

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_ENDPOINT = "http://localhost:9000"
_BUCKET = "paysentineliq-documents"


def _settings() -> Settings:
    return Settings(
        app_env="local",
        s3_endpoint_url=_ENDPOINT,
        s3_region="us-east-1",
        s3_bucket=_BUCKET,
        s3_access_key_id="CHANGE_ME",
        s3_secret_access_key="CHANGE_ME",
    )


def _client() -> Any:
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


async def test_s3_put_get_presign_delete_roundtrip() -> None:
    adapter = S3StorageAdapter(
        _settings(),
        create_bucket_if_missing=True,
    )
    await adapter.ensure_bucket()
    key = f"test/{uuid4()}/original.txt"
    payload = b"storage roundtrip"
    client = _client()

    try:
        await adapter.put(
            key,
            io.BytesIO(payload),
            content_type="text/plain",
            size=len(payload),
            metadata={"original_name": "roundtrip.txt"},
        )

        head = client.head_object(Bucket=_BUCKET, Key=key)
        assert head["ContentLength"] == len(payload)
        assert head.get("ServerSideEncryption") == "AES256"

        chunks = [chunk async for chunk in adapter.get_stream(key)]
        assert b"".join(chunks) == payload

        url = await adapter.presigned_get_url(key, expires_in=60)
        assert "X-Amz-Expires=60" in url
        async with httpx.AsyncClient(timeout=10.0) as http:
            response = await http.get(url)
        assert response.content == payload

        await adapter.delete(key)
        with pytest.raises(ClientError):
            client.head_object(Bucket=_BUCKET, Key=key)
    finally:
        client.delete_object(Bucket=_BUCKET, Key=key)
