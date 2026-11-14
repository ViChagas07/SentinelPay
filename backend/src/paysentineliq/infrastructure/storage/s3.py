import asyncio
import logging
from collections.abc import AsyncIterator, Mapping
from typing import BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from paysentineliq.application.errors import StorageUnavailableError
from paysentineliq.infrastructure.config import Settings

_logger = logging.getLogger("paysentineliq")

_CHUNK_SIZE = 64 * 1024


class S3StorageAdapter:
    def __init__(
        self,
        settings: Settings,
        *,
        create_bucket_if_missing: bool = False,
    ) -> None:
        self._bucket = settings.s3_bucket
        self._create_bucket_if_missing = create_bucket_if_missing
        self._region = settings.s3_region
        endpoint_url = settings.s3_endpoint_url or None
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": ("path" if endpoint_url else "auto")},
            ),
        )

    async def ensure_bucket(self) -> None:
        try:
            await asyncio.to_thread(self._ensure_bucket_sync)
        except (BotoCoreError, ClientError) as exc:
            _logger.error("s3_bucket_check_failed")
            raise StorageUnavailableError() from exc

    def _ensure_bucket_sync(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if not self._create_bucket_if_missing or code not in {
                "404",
                "NoSuchBucket",
                "NotFound",
            }:
                raise

        if self._region == "us-east-1":
            self._client.create_bucket(Bucket=self._bucket)
        else:
            self._client.create_bucket(
                Bucket=self._bucket,
                CreateBucketConfiguration={"LocationConstraint": self._region},
            )

    async def put(
        self,
        key: str,
        stream: BinaryIO,
        *,
        content_type: str,
        size: int,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        def _put() -> None:
            stream.seek(0)
            extra_args: dict[str, object] = {
                "ContentType": content_type,
                "ServerSideEncryption": "AES256",
            }
            if metadata:
                extra_args["Metadata"] = dict(metadata)
            self._client.upload_fileobj(
                stream,
                self._bucket,
                key,
                ExtraArgs=extra_args,
            )

        try:
            await asyncio.to_thread(_put)
        except (BotoCoreError, ClientError) as exc:
            _logger.error("s3_put_failed")
            raise StorageUnavailableError() from exc

    async def get_stream(self, key: str) -> AsyncIterator[bytes]:
        try:
            response = await asyncio.to_thread(
                self._client.get_object,
                Bucket=self._bucket,
                Key=key,
            )
        except (BotoCoreError, ClientError) as exc:
            _logger.error("s3_get_failed")
            raise StorageUnavailableError() from exc

        body = response["Body"]
        try:
            while True:
                chunk = await asyncio.to_thread(body.read, _CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(body.close)

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.delete_object,
                Bucket=self._bucket,
                Key=key,
            )
        except (BotoCoreError, ClientError) as exc:
            _logger.error("s3_delete_failed")
            raise StorageUnavailableError() from exc

    async def presigned_get_url(
        self,
        key: str,
        *,
        expires_in: int,
    ) -> str:
        try:
            url: str = await asyncio.to_thread(
                self._client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except (BotoCoreError, ClientError) as exc:
            _logger.error("s3_presign_failed")
            raise StorageUnavailableError() from exc
        return url
