import argparse
import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from paysentineliq.application.commands.hybrid_knowledge_ingestion import (  # noqa: E402
    HybridKnowledgeIngestionHandler,
)
from paysentineliq.application.commands.knowledge_ingestion import (  # noqa: E402
    IngestKnowledgeCommand,
)
from paysentineliq.application.errors import RagUnavailableError  # noqa: E402
from paysentineliq.application.queries.hybrid_retrieval import HybridRetriever  # noqa: E402
from paysentineliq.application.queries.knowledge_retrieval import KnowledgeQuery  # noqa: E402
from paysentineliq.domain.knowledge_chunking import ChunkingConfig  # noqa: E402
from paysentineliq.infrastructure.config import Settings  # noqa: E402
from paysentineliq.infrastructure.rag.cli_env import (  # noqa: E402
    load_env_file,
    local_database_url,
)
from paysentineliq.infrastructure.rag.pgvector_hybrid import (  # noqa: E402
    PGVectorHybridStore,
)
from paysentineliq.infrastructure.rag.pinecone_hybrid import (  # noqa: E402
    PineconeHybridVectorStore,
)
from paysentineliq.infrastructure.rag.source import KnowledgeFileSource  # noqa: E402
from paysentineliq.infrastructure.retrieval.bge_m3 import BgeM3Embedder  # noqa: E402
from paysentineliq.infrastructure.retrieval.errors import (  # noqa: E402
    ONNX_FLOAT_FILE,
    ONNX_INT8_FILE,
    SPARSE_WEIGHT_FILE,
    TOKENIZER_FILE,
)


def _model_dir(settings: Settings) -> Path:
    path = Path(settings.retrieval_model_dir)
    return path if path.is_absolute() else ROOT / path


def _dry_run(settings: Settings, backend: str) -> int:
    model_dir = _model_dir(settings) / "bge-m3"
    required = (
        model_dir / TOKENIZER_FILE,
        model_dir / SPARSE_WEIGHT_FILE,
    )
    onnx_files = (model_dir / ONNX_INT8_FILE, model_dir / ONNX_FLOAT_FILE)
    print(f"model_dir={model_dir}")
    print(f"backend={backend}")
    print(f"tokenizer={required[0].is_file()}")
    print(f"sparse_weights={required[1].is_file()}")
    if backend == "onnx":
        existing = [path.name for path in onnx_files if path.is_file()]
        print(f"onnx_model={','.join(existing) if existing else 'missing'}")
        return 0 if all(path.is_file() for path in required) and existing else 1
    print("pytorch_files=verificados na carga")
    return 0 if all(path.is_file() for path in required) else 1


async def _run(args: argparse.Namespace) -> int:
    settings = Settings()
    if settings.app_env != "local":
        raise SystemExit("reindex-kb only runs with APP_ENV=local")
    backend = args.backend or settings.embedder_backend
    model_dir = _model_dir(settings)
    if args.dry_run:
        return _dry_run(settings, backend)

    embedder = BgeM3Embedder(
        model_dir=model_dir / "bge-m3",
        backend=backend,
        batch_size=args.batch_size or settings.batch_size,
        torch_num_threads=settings.torch_num_threads,
    )
    engine = None
    try:
        await asyncio.to_thread(embedder.load)
        if not embedder.status.loaded or not embedder.sparse_status.loaded:
            print(
                f"FALHA: modelo indisponivel dense={embedder.status.error} "
                f"sparse={embedder.sparse_status.error}",
                file=sys.stderr,
            )
            return 1

        if settings.vector_store == "pgvector":
            engine = create_async_engine(settings.database_url)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            store = PGVectorHybridStore(factory)
        else:
            try:
                store = PineconeHybridVectorStore.from_settings(settings)
            except (RagUnavailableError, ImportError) as exc:
                print(f"FALHA: {exc}", file=sys.stderr)
                return 1

        source = KnowledgeFileSource(Path(args.knowledge_root))
        handler = HybridKnowledgeIngestionHandler(
            source,
            embedder,
            embedder,
            store,
            ChunkingConfig(
                target_chars=settings.rag_chunk_size,
                overlap_chars=settings.rag_chunk_overlap,
            ),
            hybrid_embedder=embedder,
        )
        report = await handler.handle(IngestKnowledgeCommand())
        print(
            f"embedding={embedder.model_id} backend={backend} dimension={embedder.dimension} "
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
            retriever = HybridRetriever(
                embedder,
                embedder,
                store,
                hybrid_embedder=embedder,
                default_limit=settings.retrieval_top_k,
                fusion=settings.hybrid_fusion,
                rrf_k=settings.hybrid_rrf_k,
                dense_weight=settings.hybrid_dense_weight,
                sparse_weight=settings.hybrid_sparse_weight,
            )
            result = await retriever.retrieve(
                KnowledgeQuery(
                    text=args.query,
                    limit=settings.retrieval_top_k,
                ),
            )
            print(
                f"query={args.query} mode={result.retrieval_mode} "
                f"rag_unavailable={result.rag_unavailable}",
            )
            for passage in result.passages:
                citation = passage.citation
                print(
                    f"- document={citation.document_key} section={citation.section} "
                    f"score={passage.score:.6f} dense={passage.dense_score} "
                    f"sparse={passage.sparse_score}",
                )
                print(f"  {passage.content[:240]}")
        return 1 if report.failures else 0
    finally:
        await embedder.aclose()
        if engine is not None:
            await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reindexa os documentos de knowledge/ com BGE-M3 dense 1024 e esparso, "
            "de forma idempotente. Os modelos ficam em RETRIEVAL_MODEL_DIR."
        ),
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / ".env.example",
    )
    parser.add_argument(
        "--knowledge-root",
        type=Path,
        default=ROOT / "knowledge",
    )
    parser.add_argument("--backend", choices=("onnx", "pytorch"), default=None)
    parser.add_argument("--batch-size", type=int, default=0)
    parser.add_argument("--query", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.batch_size < 0:
        parser.error("--batch-size deve ser nao negativo")
    if not args.env_file.is_file():
        raise SystemExit(f"env file not found: {args.env_file}")
    load_env_file(args.env_file)
    os.environ["DATABASE_URL"] = local_database_url()
    os.environ.setdefault("APP_ENV", "local")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
