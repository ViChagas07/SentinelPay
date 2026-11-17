import argparse
import asyncio
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paysentineliq.application.commands.knowledge_ingestion import (
    IngestKnowledgeCommand,
    IngestKnowledgeHandler,
)
from paysentineliq.application.ports.embedding import EmbeddingPort
from paysentineliq.application.ports.vector_store import VectorStorePort
from paysentineliq.application.queries.knowledge_retrieval import (
    KnowledgeQuery,
    KnowledgeRetriever,
)
from paysentineliq.domain.knowledge_chunking import ChunkingConfig
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.rag.cli_env import (
    load_env_file,
    local_database_url,
)
from paysentineliq.infrastructure.rag.embeddings import OpenAICompatibleEmbedding
from paysentineliq.infrastructure.rag.fake_embedding import (
    DeterministicHashEmbedding,
)
from paysentineliq.infrastructure.rag.pinecone import PineconeVectorStore
from paysentineliq.infrastructure.rag.source import KnowledgeFileSource


async def _run(args: argparse.Namespace) -> int:
    settings = Settings()
    if settings.app_env != "local":
        raise SystemExit("ingest-knowledge only runs with APP_ENV=local")
    if settings.embedding_dim <= 0:
        raise SystemExit("EMBEDDING_DIM must be a positive integer")
    fake = args.fake_embedder or settings.rag_fake_embedder
    embedder: EmbeddingPort
    if fake:
        embedder = DeterministicHashEmbedding(dimension=settings.embedding_dim)
        embedding_label = "fake"
    else:
        if (
            not settings.embedding_base_url
            or not settings.embedding_model
            or "CHANGE_ME" in settings.embedding_model
        ):
            raise SystemExit("EMBEDDING_BASE_URL/EMBEDDING_MODEL are not configured")
        embedder = OpenAICompatibleEmbedding(
            base_url=settings.embedding_base_url,
            model=settings.embedding_model,
            dimension=settings.embedding_dim,
            api_key=settings.embedding_api_key,
            timeout_seconds=settings.embedding_timeout_seconds,
            batch_size=settings.embedding_batch_size,
            max_retries=settings.embedding_max_retries,
            backoff_seconds=settings.embedding_retry_backoff_seconds,
        )
        embedding_label = settings.embedding_model

    engine = None
    store: VectorStorePort
    if settings.vector_store == "pgvector":
        engine = create_async_engine(settings.database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        from paysentineliq.infrastructure.rag.pgvector import PGVectorStore

        store = PGVectorStore(factory, dimension=settings.embedding_dim)
    else:
        store = PineconeVectorStore.from_settings(settings)

    source = KnowledgeFileSource(Path(args.knowledge_root))
    handler = IngestKnowledgeHandler(
        source,
        embedder,
        store,
        ChunkingConfig(
            target_chars=settings.rag_chunk_size,
            overlap_chars=settings.rag_chunk_overlap,
        ),
    )
    try:
        report = await handler.handle(IngestKnowledgeCommand())
        print(
            f"embedding={embedding_label} dimension={settings.embedding_dim} "
            f"vector_store={settings.vector_store}",
        )
        print(
            f"documents={report.documents} chunks={report.chunks} "
            f"skipped={report.skipped_documents} failures={len(report.failures)} "
            f"elapsed={report.elapsed_seconds:.2f}s",
        )
        if report.warnings:
            print(f"warnings={','.join(report.warnings)}")
        for failure in report.failures:
            print(f"failure={failure.document_key}:{failure.reason}")

        if args.query:
            retriever = KnowledgeRetriever(embedder, store)
            result = await retriever.retrieve(
                KnowledgeQuery(text=args.query, limit=5),
            )
            print(f"query={args.query} rag_unavailable={result.rag_unavailable}")
            for passage in result.passages:
                citation = passage.citation
                print(
                    f"- document={citation.document_key} section={citation.section} "
                    f"provenance={citation.provenance.value} "
                    f"authoritative={citation.authoritative} score={passage.score:.4f}",
                )
                print(f"  {passage.content[:240]}")
        return 1 if report.failures else 0
    finally:
        close = getattr(embedder, "aclose", None)
        if callable(close):
            await close()
        if engine is not None:
            await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest knowledge/ into the vector store.")
    parser.add_argument("--env-file", type=Path, default=Path("../.env.example"))
    parser.add_argument("--knowledge-root", type=Path, default=Path("../knowledge"))
    parser.add_argument("--fake-embedder", action="store_true")
    parser.add_argument("--query", default="")
    args = parser.parse_args(argv)
    if not args.env_file.is_file():
        raise SystemExit(f"env file not found: {args.env_file}")
    load_env_file(args.env_file)
    os.environ["DATABASE_URL"] = local_database_url()
    os.environ.setdefault("APP_ENV", "local")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
