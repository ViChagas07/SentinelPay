import argparse
import asyncio
import json
import os
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from eval_retrieval import EvalItem, load_items, percentile  # noqa: E402

from paysentineliq.application.queries.hybrid_retrieval import HybridRetriever  # noqa: E402
from paysentineliq.application.queries.knowledge_retrieval import KnowledgeQuery  # noqa: E402
from paysentineliq.infrastructure.config import Settings  # noqa: E402
from paysentineliq.infrastructure.rag.cli_env import (  # noqa: E402
    load_env_file,
    local_database_url,
)
from paysentineliq.infrastructure.rag.pgvector_hybrid import PGVectorHybridStore  # noqa: E402
from paysentineliq.infrastructure.rag.source import KnowledgeFileSource  # noqa: E402
from paysentineliq.infrastructure.retrieval.bge_m3 import BgeM3Embedder  # noqa: E402
from paysentineliq.infrastructure.retrieval.bge_reranker import BgeRerankerV2M3  # noqa: E402

_START = "<!-- rerank-benchmark:start -->"
_END = "<!-- rerank-benchmark:end -->"


@dataclass(frozen=True)
class CandidateSet:
    item: EvalItem
    documents: tuple[str, ...]
    contents: tuple[str, ...]


def _benchmark_items(items: list[EvalItem]) -> list[EvalItem]:
    indices = (0, 10, 25)
    return [items[index] for index in indices]


def _candidate_recall(
    items: list[EvalItem],
    candidates: dict[str, CandidateSet],
    k: int,
) -> float:
    recalls: list[float] = []
    for item in items:
        candidates_for_item = candidates[item.id].documents[:k]
        expected = set(item.expected_documents)
        recalls.append(len(set(candidates_for_item) & expected) / len(expected))
    return statistics.fmean(recalls)


def _token_lengths(
    items: list[EvalItem],
    candidates: dict[str, CandidateSet],
    tokenizer_file: Path,
) -> list[int]:
    tokenizer = Tokenizer.from_file(str(tokenizer_file))
    lengths: list[int] = []
    for item in items:
        for content in candidates[item.id].contents:
            encoding = tokenizer.encode(item.question, content)
            lengths.append(len(encoding.ids))
    return lengths


async def _latency_for_precision(
    *,
    precision: str,
    model_dir: Path,
    settings: Settings,
    queries: list[EvalItem],
    candidates: dict[str, CandidateSet],
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for max_length in (256, 384, 512):
        reranker = BgeRerankerV2M3(
            model_dir=model_dir,
            backend="onnx",
            batch_size=settings.batch_size,
            max_length=max_length,
            torch_num_threads=settings.torch_num_threads,
        )
        print(f"loading {precision} max_length={max_length}")
        await asyncio.to_thread(reranker.load)
        if not reranker.status.loaded:
            raise SystemExit(f"failed to load {precision} reranker: {reranker.status.error}")
        first = queries[0]
        await reranker.rerank(
            first.question,
            candidates[first.id].contents[:10],
            top_n=5,
        )
        for k in (10, 15, 25):
            latencies: list[float] = []
            for item in queries:
                started = perf_counter()
                await reranker.rerank(
                    item.question,
                    candidates[item.id].contents[:k],
                    top_n=5,
                )
                latencies.append((perf_counter() - started) * 1000.0)
            results.append(
                {
                    "precision": precision,
                    "max_length": max_length,
                    "k": k,
                    "p50_ms": percentile(latencies, 50),
                    "p95_ms": percentile(latencies, 95),
                    "queries": len(latencies),
                },
            )
            print(
                f"{precision} max_length={max_length} k={k} "
                f"p50={results[-1]['p50_ms']:.2f} p95={results[-1]['p95_ms']:.2f}",
            )
        await reranker.aclose()
    return results


def _choose_recommendation(
    *,
    candidate_recall: dict[int, float],
    coverage: dict[int, float],
    latency: list[dict[str, object]],
) -> dict[str, object]:
    best_candidate = max(candidate_recall.values())
    k = 25
    for candidate in (10, 15, 25):
        if candidate_recall[candidate] >= best_candidate - 0.01:
            k = candidate
            break
    covered_lengths = [candidate for candidate in (256, 384, 512) if coverage[candidate] >= 0.95]
    options = [
        item
        for item in latency
        if item["precision"] == "int8" and item["k"] == k and item["max_length"] in covered_lengths
    ]
    selected = min(
        options,
        key=lambda item: (
            float(item["p50_ms"]),
            -coverage[int(item["max_length"])],
        ),
    )
    max_length = int(selected["max_length"])
    return {
        "precision": "int8",
        "max_length": max_length,
        "k": k,
        "p50_ms": selected["p50_ms"],
        "p95_ms": selected["p95_ms"],
        "rationale": (
            "int8 pelo custo e pela regra de CPU; K escolhido como o menor "
            "com recall de candidatos a no maximo 1 ponto do melhor; entre "
            "os max_length com cobertura de tokens >= 95%, escolhido o de "
            f"menor p50 ({max_length})."
        ),
    }


def _render_section(
    *,
    query_count: int,
    candidate_recall: dict[int, float],
    coverage: dict[int, float],
    latency: list[dict[str, object]],
    recommendation: dict[str, object],
) -> str:
    lines = [
        _START,
        "## Benchmark de rerank (K, max_length, precisao)",
        "",
        f"Consultas medidas: {query_count}. Latencia medida apenas no rerank, "
        "com candidatos do estagio 1 (RRF, top-25), em CPU.",
        "",
        "### Recall de candidatos do estagio 1",
        "",
        "| K | Recall de candidatos |",
        "| ---: | ---: |",
    ]
    for k in (10, 15, 25):
        lines.append(f"| {k} | {candidate_recall[k]:.4f} |")
    lines.extend(
        [
            "",
            "### Cobertura de tokens por max_length",
            "",
            "| max_length | Pares sem truncamento |",
            "| ---: | ---: |",
        ],
    )
    for max_length in (256, 384, 512):
        lines.append(f"| {max_length} | {coverage[max_length]:.4f} |")
    lines.extend(
        [
            "",
            "### Latencia por configuracao",
            "",
            "| Precisao | max_length | K | p50 (ms) | p95 (ms) |",
            "| --- | ---: | ---: | ---: | ---: |",
        ],
    )
    for row in latency:
        lines.append(
            f"| {row['precision']} | {row['max_length']} | {row['k']} | "
            f"{row['p50_ms']:.2f} | {row['p95_ms']:.2f} |",
        )
    lines.extend(
        [
            "",
            "### Recomendacao",
            "",
            (
                f"**{recommendation['precision']}, K={recommendation['k']}, "
                f"max_length={recommendation['max_length']}**: "
                f"p50 {recommendation['p50_ms']:.2f} ms, "
                f"p95 {recommendation['p95_ms']:.2f} ms. "
                f"{recommendation['rationale']}"
            ),
            "",
            _END,
            "",
        ],
    )
    return "\n".join(lines)


def _update_results_file(path: Path, section: str) -> None:
    if not path.is_file():
        (path.parent / "RERANK_BENCHMARK.md").write_text(section, encoding="utf-8")
        return
    text = path.read_text(encoding="utf-8")
    if _START in text and _END in text:
        before, rest = text.split(_START, 1)
        _, after = rest.split(_END, 1)
        new_text = before + section + after.lstrip("\n")
    else:
        marker = "## Limitacoes e nao validado"
        if marker in text:
            before, after = text.split(marker, 1)
            new_text = before + section + marker + after
        else:
            new_text = text.rstrip() + "\n\n" + section
    path.write_text(new_text, encoding="utf-8")


async def run(args: argparse.Namespace) -> int:
    if args.render_only:
        payload_text = await asyncio.to_thread(
            Path(args.json_output).read_text,
            encoding="utf-8",
        )
        payload = json.loads(payload_text)
        candidate_recall = {
            int(key): float(value) for key, value in payload["candidate_recall"].items()
        }
        coverage = {int(key): float(value) for key, value in payload["truncation_coverage"].items()}
        recommendation = _choose_recommendation(
            candidate_recall=candidate_recall,
            coverage=coverage,
            latency=payload["latency"],
        )
        payload["recommendation"] = recommendation
        section = _render_section(
            query_count=len(payload["queries"]),
            candidate_recall=candidate_recall,
            coverage=coverage,
            latency=payload["latency"],
            recommendation=recommendation,
        )
        _update_results_file(Path(args.output), section)
        await asyncio.to_thread(
            Path(args.json_output).write_text,
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("benchmark section re-rendered", recommendation)
        return 0
    settings = Settings()
    if settings.app_env != "local":
        raise SystemExit("benchmark only runs with APP_ENV=local")
    model_root = Path(settings.retrieval_model_dir)
    if not model_root.is_absolute():
        model_root = ROOT / model_root
    known_documents = {
        document.key for document in KnowledgeFileSource(ROOT / "knowledge").scan().documents
    }
    items = load_items(Path(args.eval_file), known_documents)
    benchmark_items = _benchmark_items(items)

    embedder = BgeM3Embedder(
        model_dir=model_root / "bge-m3",
        backend="onnx",
        batch_size=settings.batch_size,
        torch_num_threads=settings.torch_num_threads,
    )
    engine = None
    try:
        print("loading embedder")
        await asyncio.to_thread(embedder.load)
        if not embedder.status.loaded or not embedder.sparse_status.loaded:
            print("FALHA: embedder indisponivel", file=sys.stderr)
            return 1
        engine = create_async_engine(settings.database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        store = PGVectorHybridStore(factory)
        stage1 = HybridRetriever(
            embedder,
            embedder,
            store,
            hybrid_embedder=embedder,
            default_limit=settings.retrieval_top_k,
            fusion="rrf",
            rrf_k=settings.hybrid_rrf_k,
        )
        candidates: dict[str, CandidateSet] = {}
        print("collecting stage 1 candidates")
        for item in items:
            result = await stage1.retrieve(
                KnowledgeQuery(text=item.question, limit=settings.retrieval_top_k),
            )
            candidates[item.id] = CandidateSet(
                item=item,
                documents=tuple(passage.citation.document_key for passage in result.passages),
                contents=tuple(passage.content for passage in result.passages),
            )
        await embedder.aclose()

        candidate_recall = {k: _candidate_recall(items, candidates, k) for k in (10, 15, 25)}
        token_lengths = _token_lengths(
            items,
            candidates,
            model_root / "bge-reranker-v2-m3" / "tokenizer.json",
        )
        coverage = {
            limit: sum(length <= limit for length in token_lengths) / len(token_lengths)
            for limit in (256, 384, 512)
        }
        print("candidate recall", candidate_recall)
        print("coverage", coverage)

        int8_latency = await _latency_for_precision(
            precision="int8",
            model_dir=model_root / "bge-reranker-v2-m3",
            settings=settings,
            queries=benchmark_items,
            candidates=candidates,
        )
        fp32_dir = model_root / "bge-reranker-v2-m3-fp32"
        if not fp32_dir.is_dir():
            print(
                f"FALHA: diretorio fp32 ausente: {fp32_dir}",
                file=sys.stderr,
            )
            return 1
        fp32_latency = await _latency_for_precision(
            precision="fp32",
            model_dir=fp32_dir,
            settings=settings,
            queries=benchmark_items,
            candidates=candidates,
        )
        latency = int8_latency + fp32_latency
        recommendation = _choose_recommendation(
            candidate_recall=candidate_recall,
            coverage=coverage,
            latency=latency,
        )
        section = _render_section(
            query_count=len(benchmark_items),
            candidate_recall=candidate_recall,
            coverage=coverage,
            latency=latency,
            recommendation=recommendation,
        )
        _update_results_file(Path(args.output), section)
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "queries": [item.id for item in benchmark_items],
            "candidate_recall": {str(k): value for k, value in candidate_recall.items()},
            "truncation_coverage": {str(limit): value for limit, value in coverage.items()},
            "latency": latency,
            "recommendation": recommendation,
        }
        await asyncio.to_thread(
            Path(args.json_output).write_text,
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("benchmark written", recommendation)
        return 0
    finally:
        await embedder.aclose()
        if engine is not None:
            await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mede latencia do reranker variando K, max_length e precisao.",
    )
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env.example")
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=ROOT / "eval" / "retrieval_eval.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "eval" / "RESULTS.md",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=ROOT / "eval" / "rerank_benchmark.json",
    )
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()
    if not args.env_file.is_file():
        raise SystemExit(f"env file not found: {args.env_file}")
    load_env_file(args.env_file)
    os.environ["DATABASE_URL"] = local_database_url()
    os.environ.setdefault("APP_ENV", "local")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
