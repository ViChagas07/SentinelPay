import time
from dataclasses import dataclass
from pathlib import PurePosixPath

from paysentineliq.application.errors import (
    EmbeddingDimensionError,
    EmbeddingUnavailableError,
    RagUnavailableError,
)
from paysentineliq.application.ports.embedding import EmbeddingPort
from paysentineliq.application.ports.knowledge_source import KnowledgeSourcePort
from paysentineliq.application.ports.vector_store import VectorStorePort
from paysentineliq.domain.knowledge import (
    EmbeddedChunk,
    KnowledgeChunk,
    KnowledgeDocument,
)
from paysentineliq.domain.knowledge_chunking import (
    ChunkingConfig,
    chunk_markdown,
    chunk_pages,
)


@dataclass(frozen=True, slots=True)
class IngestKnowledgeCommand:
    pass


@dataclass(frozen=True, slots=True)
class DocumentFailure:
    document_key: str
    reason: str


@dataclass(frozen=True, slots=True)
class IngestReport:
    documents: int
    chunks: int
    skipped_documents: int
    failures: tuple[DocumentFailure, ...]
    warnings: tuple[str, ...]
    elapsed_seconds: float


def is_allowed_document(document: KnowledgeDocument) -> bool:
    parts = PurePosixPath(document.path).parts
    return (
        len(parts) >= 3
        and parts[0] == "knowledge"
        and parts[1] == document.category
        and ".." not in parts
    )


def failure_reason(error: Exception) -> str:
    if isinstance(error, EmbeddingDimensionError):
        return "embedding_dimension_mismatch"
    if isinstance(error, EmbeddingUnavailableError):
        return "embedding_unavailable"
    if isinstance(error, RagUnavailableError):
        return "vector_store_unavailable"
    return "processing_failed"


def chunk_document(
    document: KnowledgeDocument,
    config: ChunkingConfig,
) -> tuple[KnowledgeChunk, ...]:
    if document.format == "markdown":
        text = "\n".join(page.text for page in document.pages)
        return chunk_markdown(
            text,
            document_key=document.key,
            config=config,
        )
    return chunk_pages(document, config)


class IngestKnowledgeHandler:
    def __init__(
        self,
        source: KnowledgeSourcePort,
        embedder: EmbeddingPort,
        store: VectorStorePort,
        config: ChunkingConfig | None = None,
    ) -> None:
        self._source = source
        self._embedder = embedder
        self._store = store
        self._config = config if config is not None else ChunkingConfig()

    def _chunks(self, document: KnowledgeDocument) -> tuple[KnowledgeChunk, ...]:
        return chunk_document(document, self._config)

    async def handle(self, command: IngestKnowledgeCommand) -> IngestReport:
        started = time.monotonic()
        scan = self._source.scan()
        failures = [
            DocumentFailure(document_key=item, reason="scan_failure") for item in scan.failures
        ]
        documents = 0
        chunks = 0
        skipped_documents = 0
        for document in scan.documents:
            if not is_allowed_document(document):
                failures.append(
                    DocumentFailure(
                        document_key=document.key,
                        reason="outside_knowledge_root",
                    ),
                )
                continue
            try:
                document_chunks = self._chunks(document)
                if not document_chunks:
                    failures.append(
                        DocumentFailure(
                            document_key=document.key,
                            reason="empty_document",
                        ),
                    )
                    continue
                vectors = await self._embedder.embed(
                    tuple(chunk.content for chunk in document_chunks),
                )
                if len(vectors) != len(document_chunks):
                    raise EmbeddingDimensionError("embedding count mismatch")
                for vector in vectors:
                    if len(vector) != self._embedder.dimension:
                        raise EmbeddingDimensionError("embedding dimension mismatch")
                result = await self._store.upsert_document(
                    document,
                    tuple(
                        EmbeddedChunk(chunk=chunk, embedding=vector)
                        for chunk, vector in zip(
                            document_chunks,
                            vectors,
                            strict=True,
                        )
                    ),
                )
                documents += 1
                chunks += result.chunks_written
                if result.skipped:
                    skipped_documents += 1
            except Exception as error:
                failures.append(
                    DocumentFailure(
                        document_key=document.key,
                        reason=failure_reason(error),
                    ),
                )
        return IngestReport(
            documents=documents,
            chunks=chunks,
            skipped_documents=skipped_documents,
            failures=tuple(failures),
            warnings=scan.skipped_directories,
            elapsed_seconds=time.monotonic() - started,
        )
