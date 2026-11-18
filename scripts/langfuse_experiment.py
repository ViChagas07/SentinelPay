import argparse
import asyncio
import contextlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from eval_retrieval import DenseStage1, EvalItem, load_items, to_retrieved  # noqa: E402
from langfuse import Langfuse  # noqa: E402

from paysentineliq.application.queries.hybrid_retrieval import HybridRetriever  # noqa: E402
from paysentineliq.application.queries.knowledge_retrieval import (  # noqa: E402
    KnowledgeQuery,
    KnowledgeRetrievalResult,
)
from paysentineliq.application.queries.two_stage_retrieval import TwoStageRetriever  # noqa: E402
from paysentineliq.infrastructure.config import Settings  # noqa: E402
from paysentineliq.infrastructure.rag.cli_env import (  # noqa: E402
    load_env_file,
    local_database_url,
)
from paysentineliq.infrastructure.rag.pgvector_hybrid import PGVectorHybridStore  # noqa: E402
from paysentineliq.infrastructure.rag.source import KnowledgeFileSource  # noqa: E402
from paysentineliq.infrastructure.retrieval.bge_m3 import BgeM3Embedder  # noqa: E402
from paysentineliq.infrastructure.retrieval.bge_reranker import BgeRerankerV2M3  # noqa: E402

_DOCUMENT_ID_RE = re.compile(r"\b\d{11,}\b")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


@dataclass(frozen=True)
class ExperimentMode:
    slug: str
    name: str
    stage1: Literal["dense", "rrf"]
    rerank: bool


def _load_langfuse_env(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        if key.startswith("LANGFUSE_"):
            os.environ[key] = value.strip().strip('"').strip("'")


def _assert_public_dataset(items: list[EvalItem]) -> None:
    for item in items:
        if _DOCUMENT_ID_RE.search(item.question) or _EMAIL_RE.search(item.question):
            raise SystemExit(
                f"eval item {item.id} contains a possible personal identifier; "
                "the Langfuse dataset must stay public",
            )


def _ensure_dataset(
    client: Langfuse,
    dataset_name: str,
    items: list[EvalItem],
) -> Any:
    try:
        dataset = client.get_dataset(dataset_name)
    except Exception:
        client.create_dataset(
            name=dataset_name,
            description="Perguntas publicas de retrieval do SentinelPay.",
            metadata={"source": "eval/retrieval_eval.jsonl", "pii": "none"},
        )
        client.flush()
        dataset = client.get_dataset(dataset_name)
    existing = {item.id for item in dataset.items}
    created = 0
    for item in items:
        if item.id in existing:
            continue
        client.create_dataset_item(
            dataset_name=dataset_name,
            id=item.id,
            input={
                "question": item.question,
                "language": item.language,
                "domain": item.domain,
            },
            expected_output={"documents": item.expected_documents},
            metadata={
                "id": item.id,
                "language": item.language,
                "domain": item.domain,
            },
        )
        created += 1
    if created:
        client.flush()
    print(f"dataset {dataset_name}: {created} item(ns) criado(s), {len(existing)} existente(s)")
    return client.get_dataset(dataset_name)


def _evaluator(
    *,
    output: Any,
    expected_output: Any,
    **_: Any,
) -> list[dict[str, Any]]:
    result = output if isinstance(output, dict) else {}
    expected_payload = expected_output if isinstance(expected_output, dict) else {}
    documents = [str(document) for document in result.get("documents", [])][:5]
    expected = {str(document) for document in expected_payload.get("documents", [])}
    recall = len(set(documents) & expected) / len(expected) if expected else 0.0
    reciprocal_rank = 0.0
    for rank, document in enumerate(documents, start=1):
        if document in expected:
            reciprocal_rank = 1.0 / rank
            break
    return [
        {"name": "recall_at_5", "value": recall},
        {"name": "mrr", "value": reciprocal_rank},
        {
            "name": "top1_match",
            "value": 1.0 if documents and documents[0] in expected else 0.0,
        },
    ]


def _build_retriever(
    mode: ExperimentMode,
    settings: Settings,
    embedder: BgeM3Embedder,
    reranker: BgeRerankerV2M3,
    store: PGVectorHybridStore,
    eval_k: int,
) -> Any:
    if mode.stage1 == "dense":
        stage1: Any = DenseStage1(
            embedder,
            store,
            default_limit=settings.retrieval_top_k,
        )
    else:
        stage1 = HybridRetriever(
            embedder,
            embedder,
            store,
            hybrid_embedder=embedder,
            default_limit=settings.retrieval_top_k,
            fusion="rrf",
            rrf_k=settings.hybrid_rrf_k,
        )
    if not mode.rerank:
        return stage1
    return TwoStageRetriever(
        stage1,
        reranker=reranker,
        rerank_enabled=True,
        top_n=eval_k,
        timeout_seconds=settings.rerank_timeout_seconds,
    )


async def _run_item(
    mode: ExperimentMode,
    settings: Settings,
    embedder: BgeM3Embedder,
    reranker: BgeRerankerV2M3,
    eval_k: int,
    item: Any,
) -> dict[str, Any]:
    payload = item.input if isinstance(item.input, dict) else {}
    question = str(payload.get("question", item.input))
    engine = create_async_engine(settings.database_url)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        store = PGVectorHybridStore(factory)
        retriever = _build_retriever(
            mode,
            settings,
            embedder,
            reranker,
            store,
            eval_k,
        )
        started = perf_counter()
        result: KnowledgeRetrievalResult = await retriever.retrieve(
            KnowledgeQuery(text=question, limit=settings.retrieval_top_k),
        )
        latency_ms = (perf_counter() - started) * 1000.0
        retrieved = to_retrieved(list(result.passages))[:eval_k]
        return {
            "documents": [entry.document_key for entry in retrieved],
            "scores": [entry.score for entry in retrieved],
            "latency_ms": latency_ms,
            "retrieval_mode": result.retrieval_mode,
            "rerank_applied": result.rerank_applied,
            "rerank_fallback": result.rerank_fallback,
            "rerank_top1_changed": result.rerank_top1_changed,
        }
    finally:
        await engine.dispose()


def _task_for(
    mode: ExperimentMode,
    settings: Settings,
    embedder: BgeM3Embedder,
    reranker: BgeRerankerV2M3,
    eval_k: int,
) -> Any:
    async def task(*, item: Any, **_: Any) -> dict[str, Any]:
        return await _run_item(
            mode,
            settings,
            embedder,
            reranker,
            eval_k,
            item,
        )

    return task


def _summarize(result: Any) -> dict[str, Any]:
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    top1: list[float] = []
    latencies: list[float] = []
    failed = 0
    for item in result.item_results:
        output = item.output
        if not isinstance(output, dict):
            failed += 1
            continue
        latency = output.get("latency_ms")
        if isinstance(latency, (int, float)):
            latencies.append(float(latency))
        for evaluation in item.evaluations:
            if not isinstance(evaluation, dict):
                continue
            name = evaluation.get("name")
            value = evaluation.get("value")
            if name == "recall_at_5" and isinstance(value, (int, float)):
                recalls.append(float(value))
            elif name == "mrr" and isinstance(value, (int, float)):
                reciprocal_ranks.append(float(value))
            elif name == "top1_match" and isinstance(value, (int, float)):
                top1.append(float(value))
    return {
        "items": len(result.item_results),
        "failed_items": failed,
        "recall_at_5": sum(recalls) / len(recalls) if recalls else 0.0,
        "mrr": (
            sum(reciprocal_ranks) / len(reciprocal_ranks)
            if reciprocal_ranks
            else 0.0
        ),
        "top1_match": sum(top1) / len(top1) if top1 else 0.0,
        "p50_latency_ms": (
            sorted(latencies)[len(latencies) // 2] if latencies else 0.0
        ),
        "scored_items": len(recalls),
    }


async def _load_models(
    embedder: BgeM3Embedder,
    reranker: BgeRerankerV2M3,
    settings: Settings,
) -> None:
    print("loading models")
    await asyncio.to_thread(embedder.load)
    await asyncio.to_thread(reranker.load)
    if not embedder.status.loaded or not embedder.sparse_status.loaded:
        raise SystemExit(
            f"embedder dense={embedder.status.error} sparse={embedder.sparse_status.error}",
        )
    if not reranker.status.loaded:
        raise SystemExit(f"reranker {reranker.status.error}")
    engine = create_async_engine(settings.database_url)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            count = await session.scalar(
                text("SELECT count(*) FROM knowledge_hybrid_chunks"),
            )
        if not count:
            raise SystemExit("knowledge_hybrid_chunks esta vazio; rode make reindex-kb")
        print(f"hybrid chunks: {count}")
    finally:
        await engine.dispose()


async def _warmup(
    modes: tuple[ExperimentMode, ...],
    settings: Settings,
    embedder: BgeM3Embedder,
    reranker: BgeRerankerV2M3,
    eval_k: int,
    question: str,
) -> None:
    engine = create_async_engine(settings.database_url)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        store = PGVectorHybridStore(factory)
        for mode in modes:
            retriever = _build_retriever(
                mode,
                settings,
                embedder,
                reranker,
                store,
                eval_k,
            )
            await retriever.retrieve(
                KnowledgeQuery(
                    text=question,
                    limit=settings.retrieval_top_k,
                ),
            )
    finally:
        await engine.dispose()


async def _close_models(
    embedder: BgeM3Embedder,
    reranker: BgeRerankerV2M3,
) -> None:
    await embedder.aclose()
    await reranker.aclose()


def run(args: argparse.Namespace) -> int:
    settings = Settings()
    if settings.app_env != "local":
        raise SystemExit("Langfuse experiments only run with APP_ENV=local")
    if args.rerank_timeout is not None:
        settings = settings.model_copy(
            update={"rerank_timeout_seconds": args.rerank_timeout},
        )
    public_key = settings.langfuse_public_key.strip()
    secret_key = settings.langfuse_secret_key.strip()
    if not public_key or not secret_key:
        raise SystemExit(
            "LANGFUSE_PUBLIC_KEY e LANGFUSE_SECRET_KEY sao obrigatorias; "
            "exporte-as ou use --langfuse-env-file",
        )
    model_root = Path(settings.retrieval_model_dir)
    if not model_root.is_absolute():
        model_root = ROOT / model_root
    known_documents = {
        document.key for document in KnowledgeFileSource(ROOT / "knowledge").scan().documents
    }
    items = load_items(Path(args.eval_file), known_documents)
    _assert_public_dataset(items)

    client = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=(
            settings.langfuse_host.strip()
            or settings.langfuse_base_url.strip()
            or "https://cloud.langfuse.com"
        ),
        environment="local",
        timeout=10,
        flush_at=10,
        flush_interval=1.0,
        sample_rate=1.0,
    )
    embedder = BgeM3Embedder(
        model_dir=model_root / "bge-m3",
        backend=args.backend,
        batch_size=settings.batch_size,
        torch_num_threads=settings.torch_num_threads,
    )
    reranker = BgeRerankerV2M3(
        model_dir=model_root / "bge-reranker-v2-m3",
        backend=args.backend,
        batch_size=settings.batch_size,
        max_length=settings.rerank_max_length,
        torch_num_threads=settings.torch_num_threads,
    )
    try:
        asyncio.run(_load_models(embedder, reranker, settings))
        modes = (
            ExperimentMode("dense", "Denso (BGE-M3)", "dense", False),
            ExperimentMode("dense-rerank", "Denso + rerank", "dense", True),
            ExperimentMode("hybrid-rrf", "Hibrido RRF", "rrf", False),
            ExperimentMode("hybrid-rerank", "Hibrido RRF + rerank", "rrf", True),
        )

        print("warmup")
        asyncio.run(
            _warmup(
                modes,
                settings,
                embedder,
                reranker,
                args.eval_k,
                items[0].question,
            ),
        )

        dataset = _ensure_dataset(client, args.dataset_name, items)
        results: list[dict[str, Any]] = []
        for mode in modes:
            print(f"running experiment {mode.name}")
            result = dataset.run_experiment(
                name=f"{args.experiment_prefix}: {mode.name}",
                run_name=f"{args.experiment_prefix}-{mode.slug}",
                description=(
                    "Experimento de retrieval do SentinelPay em CPU. "
                    f"Modo {mode.name}, top_k={settings.retrieval_top_k}, "
                    f"eval_k={args.eval_k}, backend={args.backend}."
                ),
                task=_task_for(
                    mode,
                    settings,
                    embedder,
                    reranker,
                    args.eval_k,
                ),
                evaluators=[_evaluator],
                max_concurrency=1,
                metadata={
                    "mode": mode.name,
                    "backend": args.backend,
                    "top_k": str(settings.retrieval_top_k),
                    "eval_k": str(args.eval_k),
                    "rerank_top_n": str(args.eval_k),
                },
            )
            url = getattr(result, "experiment_url", None) or getattr(
                result,
                "dataset_run_url",
                "",
            )
            results.append(
                {
                    "mode": mode.name,
                    "slug": mode.slug,
                    "experiment_url": url,
                    "items": len(result.item_results),
                    "summary": _summarize(result),
                },
            )
            print(f"{mode.name}: {url}")
        client.flush()
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "dataset": args.dataset_name,
            "experiment_prefix": args.experiment_prefix,
            "eval_k": args.eval_k,
            "top_k": settings.retrieval_top_k,
            "backend": args.backend,
            "runs": results,
        }
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"experiment report written to {output}")
        return 0
    finally:
        with contextlib.suppress(Exception):
            asyncio.run(_close_models(embedder, reranker))
        with contextlib.suppress(Exception):
            client.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publica o dataset de eval no Langfuse e roda experimentos comparaveis.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / ".env.example",
    )
    parser.add_argument(
        "--langfuse-env-file",
        type=Path,
        default=None,
        help="arquivo local do qual somente variaveis LANGFUSE_* sao lidas",
    )
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=ROOT / "eval" / "retrieval_eval.jsonl",
    )
    parser.add_argument("--dataset-name", default="retrieval-eval-v1")
    parser.add_argument("--experiment-prefix", default="sentinelpay-retrieval-v1")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "eval" / "langfuse_experiment.json",
    )
    parser.add_argument("--backend", choices=("onnx", "pytorch"), default="onnx")
    parser.add_argument("--eval-k", type=int, default=5)
    parser.add_argument("--rerank-timeout", type=float, default=None)
    args = parser.parse_args()
    if args.eval_k <= 0:
        parser.error("--eval-k deve ser positivo")
    if args.rerank_timeout is not None and args.rerank_timeout <= 0:
        parser.error("--rerank-timeout deve ser positivo")
    if not args.env_file.is_file():
        raise SystemExit(f"env file not found: {args.env_file}")
    load_env_file(args.env_file)
    os.environ["DATABASE_URL"] = local_database_url()
    os.environ.setdefault("APP_ENV", "local")
    if args.langfuse_env_file is not None:
        if not args.langfuse_env_file.is_file():
            raise SystemExit(f"langfuse env file not found: {args.langfuse_env_file}")
        _load_langfuse_env(args.langfuse_env_file)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
