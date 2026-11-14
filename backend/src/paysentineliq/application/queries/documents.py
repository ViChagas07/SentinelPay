from dataclasses import dataclass
from uuid import UUID

from paysentineliq.application.errors import DocumentNotFoundError
from paysentineliq.application.ports.document_read_repository import (
    DocumentReadRepository,
)
from paysentineliq.application.ports.storage import StoragePort


@dataclass(frozen=True, slots=True)
class GetDocumentDownloadUrlQuery:
    owner_id: UUID
    document_id: UUID


@dataclass(frozen=True, slots=True)
class DocumentDownloadUrlDTO:
    url: str
    expires_in: int


class GetDocumentDownloadUrlHandler:
    def __init__(
        self,
        read_repository: DocumentReadRepository,
        storage: StoragePort,
        *,
        presigned_ttl_seconds: int,
    ) -> None:
        if presigned_ttl_seconds <= 0:
            raise ValueError("presigned_ttl_seconds must be positive")
        self._read_repository = read_repository
        self._storage = storage
        self._presigned_ttl = presigned_ttl_seconds

    async def handle(
        self,
        query: GetDocumentDownloadUrlQuery,
    ) -> DocumentDownloadUrlDTO:
        location = await self._read_repository.get_download_location(
            query.document_id,
            query.owner_id,
        )
        if location is None:
            raise DocumentNotFoundError()

        url = await self._storage.presigned_get_url(
            location.s3_key,
            expires_in=self._presigned_ttl,
        )
        return DocumentDownloadUrlDTO(url=url, expires_in=self._presigned_ttl)
