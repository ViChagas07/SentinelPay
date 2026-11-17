import asyncio
import time

from paysentineliq.application.commands.knowledge_ingestion import (
    DocumentFailure,
    IngestKnowledgeCommand,
    IngestReport,
    chunk_document,
    failure_reason,
    is_allowed_document,
)
from paysentineliq.application.errors import EmbeddingDimensionError
from paysentineliq.application.ports.hybrid_vector_store import HybridVectorStorePort
from paysentineliq.application.ports.knowledge_source import KnowledgeSourcePort
from paysentineliq.domain.knowledge import KnowledgeChunk
from paysentineliq.domain.knowledge_chunking import ChunkingConfig
from paysentineliq.domain.ports.retrieval import (
    Embedder,
    HybridEmbeddedChunk,
    HybridEmbedder,
    SparseEmbedder,
    SparseVector,
)


class HybridKnowledgeIngestionHandler:
    def __init__(
        self,
        source: KnowledgeSourcePort,
        embedder: Embedder,
        sparse_embedder: SparseEmbedder,
        store: HybridVectorStorePort,
        config: ChunkingConfig | None = None,
        hybrid_embedder: HybridEmbedder | None = None,
    ) -> None:
        self._source = source
        self._embedder = embedder
        self._sparse_embedder = sparse_embedder
        self._store = store
        self._config = config if config is not None else ChunkingConfig()
        self._hybrid_embedder = hybrid_embedder

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
                document_chunks = chunk_document(document, self._config)
                if not document_chunks:
                    failures.append(
                        DocumentFailure(
                            document_key=document.key,
                            reason="empty_document",
                        ),
                    )
                    continue
                embedded = await self._embed(document_chunks)
                result = await self._store.upsert_hybrid_document(
                    document,
                    embedded,
                    embedding_model=self._embedder.model_id,
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

    async def _embed(
        self,
        chunks: tuple[KnowledgeChunk, ...],
    ) -> tuple[HybridEmbeddedChunk, ...]:
        texts = tuple(chunk.content for chunk in chunks)
        dense: tuple[tuple[float, ...], ...]
        sparse: tuple[SparseVector, ...]
        if self._hybrid_embedder is not None:
            dense, sparse = await self._hybrid_embedder.embed_hybrid(texts)
        else:
            dense, sparse = await asyncio.gather(
                self._embedder.embed(texts),
                self._sparse_embedder.embed_sparse(texts),
            )
        if len(dense) != len(texts) or len(sparse) != len(texts):
            raise EmbeddingDimensionError("embedding count mismatch")
        for vector in dense:
            if len(vector) != self._embedder.dimension:
                raise EmbeddingDimensionError("embedding dimension mismatch")
        return tuple(
            HybridEmbeddedChunk(
                chunk=chunk,
                dense_embedding=dense_vector,
                sparse_embedding=sparse_vector,
            )
            for chunk, dense_vector, sparse_vector in zip(
                chunks,
                dense,
                sparse,
                strict=True,
            )
        )
