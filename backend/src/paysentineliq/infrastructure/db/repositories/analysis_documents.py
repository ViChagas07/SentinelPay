from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paysentineliq.application.ports.analysis import AnalysisDocument
from paysentineliq.application.ports.storage import StoragePort
from paysentineliq.domain.document import DocumentKind
from paysentineliq.infrastructure.db.models import DocumentModel


class SqlAlchemyAnalysisDocumentAdapter:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: StoragePort,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage

    async def get(self, document_id: UUID) -> AnalysisDocument | None:
        async with self._session_factory() as session:
            model = await session.get(DocumentModel, document_id)
        if model is None:
            return None
        return AnalysisDocument(
            id=model.id,
            owner_id=model.owner_id,
            kind=DocumentKind(model.kind),
            s3_key=model.s3_key,
            content_type=model.content_type,
            size=model.size,
        )

    async def read(self, document: AnalysisDocument) -> bytes:
        chunks: list[bytes] = []
        async for chunk in self._storage.get_stream(document.s3_key):
            chunks.append(chunk)
        return b"".join(chunks)
