from collections.abc import AsyncIterator, Mapping
from typing import BinaryIO, Protocol


class StoragePort(Protocol):
    async def put(
        self,
        key: str,
        stream: BinaryIO,
        *,
        content_type: str,
        size: int,
        metadata: Mapping[str, str] | None = None,
    ) -> None: ...

    def get_stream(self, key: str) -> AsyncIterator[bytes]: ...

    async def delete(self, key: str) -> None: ...

    async def presigned_get_url(
        self,
        key: str,
        *,
        expires_in: int,
    ) -> str: ...
