import argparse
import asyncio
import contextlib
import json
import os
import platform
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from paysentineliq.application.queries.hybrid_retrieval import HybridRetriever  # noqa: E402
from paysentineliq.application.queries.knowledge_retrieval import KnowledgeQuery  # noqa: E402
from paysentineliq.application.queries.two_stage_retrieval import TwoStageRetriever  # noqa: E402
from paysentineliq.domain.knowledge import KnowledgeFilter  # noqa: E402
from paysentineliq.infrastructure.config import Settings  # noqa: E402
from paysentineliq.infrastructure.rag.cli_env import (  # noqa: E402
    load_env_file,
    local_database_url,
)
from paysentineliq.infrastructure.rag.pgvector_hybrid import PGVectorHybridStore  # noqa: E402
from paysentineliq.infrastructure.rag.source import KnowledgeFileSource  # noqa: E402
from paysentineliq.infrastructure.retrieval.bge_m3 import BgeM3Embedder  # noqa: E402
from paysentineliq.infrastructure.retrieval.bge_reranker import BgeRerankerV2M3  # noqa: E402


class EvalItem(BaseModel):
    id: str
    language: str
    domain: str
    question: str
    expected_documents: list[str] = Field(min_length=1)


@dataclass(frozen=True)
class Retrieved:
    document_key: str
    content: str
    score: float


@dataclass
class ModeRun:
    name: str
    recalls: list[float]
    rrs: list[float]
    latencies_ms: list[float]
    per_query: list[dict[str, object]]
    corrections: list[dict[str, object]]

    def summary(self) -> dict[str, object]:
        return {
            "recall_at_5": statistics.fmean(self.recalls),
            "mrr": statistics.fmean(self.rrs),
            "p50_ms": percentile(self.latencies_ms, 50),
            "p95_ms": percentile(self.latencies_ms, 95),
            "queries": len(self.recalls),
        }


def percentile(values: list[float], value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, ceil(value / 100.0 * len(ordered)) - 1))
    return ordered[index]


def load_items(path: Path, known_documents: set[str]) -> list[EvalItem]:
    items: list[EvalItem] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            item = EvalItem.model_validate_json(raw)
        except ValidationError as exc:
            raise SystemExit(f"invalid eval line {line_number}: {exc}") from exc
        if item.language not in {"pt", "es", "en"}:
            raise SystemExit(f"invalid language on line {line_number}: {item.language}")
        if item.domain not in {"febraban", "inss", "clt", "fraud"}:
            raise SystemExit(f"invalid domain on line {line_number}: {item.domain}")
        unknown = set(item.expected_documents) - known_documents
        if unknown:
            raise SystemExit(
                f"unknown expected documents on line {line_number}: {sorted(unknown)}",
            )
        items.append(item)
    if len(items) != 30:
        raise SystemExit(f"eval must contain 30 questions, found {len(items)}")
    if len({item.id for item in items}) != len(items):
        raise SystemExit("eval ids must be unique")
    if {item.language for item in items} != {"pt", "es", "en"}:
        raise SystemExit("eval must cover pt, es and en")
    if {item.domain for item in items} != {"febraban", "inss", "clt", "fraud"}:
        raise SystemExit("eval must cover febraban, inss, clt and fraud")
    return items


def score_result(
    item: EvalItem,
    retrieved: list[Retrieved],
    eval_k: int,
) -> tuple[float, float, list[str]]:
    documents = [result.document_key for result in retrieved[:eval_k]]
    expected = set(item.expected_documents)
    hits = len(set(documents) & expected)
    recall = hits / len(expected)
    reciprocal_rank = 0.0
    for rank, document in enumerate(documents, start=1):
        if document in expected:
            reciprocal_rank = 1.0 / rank
            break
    return recall, reciprocal_rank, documents


def clean_text(value: str) -> str:
    with contextlib.suppress(UnicodeEncodeError, UnicodeDecodeError):
        value = value.encode("latin-1").decode("utf-8")
    cleaned = " ".join(value.replace("—", ", ").split())
    return cleaned.replace(" ,", ",")


def first_expected_rank(item: EvalItem, documents: list[str]) -> int | None:
    expected = set(item.expected_documents)
    for rank, document in enumerate(documents, start=1):
        if document in expected:
            return rank
    return None


def to_retrieved(passages: list[object]) -> list[Retrieved]:
    retrieved: list[Retrieved] = []
    for passage in passages:
        citation = passage.citation
        retrieved.append(
            Retrieved(
                document_key=citation.document_key,
                content=passage.content,
                score=float(passage.score),
            ),
        )
    return retrieved


def build_result_markdown(
    *,
    items: list[EvalItem],
    runs: list[ModeRun],
    examples: list[dict[str, object]],
    settings: Settings,
    model_dir: Path,
    backend: str,
    rerank_timeout: float,
) -> str:
    languages = dict.fromkeys(("pt", "es", "en"), 0)
    domains = dict.fromkeys(("febraban", "inss", "clt", "fraud"), 0)
    for item in items:
        languages[item.language] += 1
        domains[item.domain] += 1
    lines = [
        "# Resultados da avaliacao de retrieval",
        "",
        "Avaliacao local em CPU dos tres modos de retrieval planejados na P17.1.",
        "",
        "## Configuracao",
        "",
        f"- Data: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Dataset: `eval/retrieval_eval.jsonl` ({len(items)} perguntas)",
        f"- Idiomas: pt={languages['pt']}, es={languages['es']}, en={languages['en']}",
        (
            "- Dominios: "
            f"febraban={domains['febraban']}, inss={domains['inss']}, "
            f"clt={domains['clt']}, fraud={domains['fraud']}"
        ),
        f"- Top-K do estagio 1: {settings.retrieval_top_k}",
        "- K da metrica: 5 (Recall@5 e MRR)",
        "- Top-N do reranker na avaliacao: 5 (producao usa RERANK_TOP_N=4)",
        f"- Timeout do reranker: {rerank_timeout:g} s",
        f"- Backend: ONNX Runtime int8 em CPU ({backend})",
        f"- Host: {platform.platform()} / {os.cpu_count()} vCPUs",
        f"- Modelos: {model_dir}",
        "- Latencia inclui embedding da consulta, busca, fusao e rerank; "
        "nao inclui carga dos modelos.",
        "- Execucao sequencial, sem cache de consulta e sem paralelismo entre queries.",
        "",
        "## Tabela",
        "",
        "| Modo | Recall@5 | MRR | p50 (ms) | p95 (ms) |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for run in runs:
        summary = run.summary()
        lines.append(
            f"| {run.name} | {summary['recall_at_5']:.4f} | {summary['mrr']:.4f} | "
            f"{summary['p50_ms']:.2f} | {summary['p95_ms']:.2f} |",
        )
    lines.extend(
        [
            "",
            "## Exemplos em que o rerank corrige o estagio 1",
            "",
        ],
    )
    if examples:
        for index, example in enumerate(examples, start=1):
            lines.extend(
                [
                    f"### Exemplo {index}: {example['id']} ({example['language']})",
                    "",
                    f"Pergunta: {example['question']}",
                    "",
                    f"Documentos esperados: {', '.join(example['expected_documents'])}",
                    "",
                    (
                        f"Estagio 1: top1=`{example['before_document']}` "
                        f"(rank esperado={example['before_rank']}, "
                        f"score={example['before_score']:.4f})"
                    ),
                    "",
                    (
                        f"Depois do rerank: top1=`{example['after_document']}` "
                        f"(rank esperado={example['after_rank']}, "
                        f"score={example['after_score']:.4f})"
                    ),
                    "",
                    f"Antes: {example['before_snippet']}",
                    "",
                    f"Depois: {example['after_snippet']}",
                    "",
                ],
            )
    else:
        lines.extend(
            [
                "Nenhuma correcao de top-1 foi observada neste conjunto. "
                "As metricas acima continuam sendo a referencia desta execucao.",
                "",
            ],
        )
    lines.extend(
        [
            "## Como reproduzir",
            "",
            "```powershell",
            "poetry -C backend run python ../scripts/reindex_kb.py "
            "--env-file ../.env.example --knowledge-root ../knowledge",
            "poetry -C backend run python ../scripts/eval_retrieval.py",
            "```",
            "",
            "## Limitacoes",
            "",
            "- 30 perguntas e 21 documentos: os numeros sao indicativos, "
            "nao um benchmark estatistico.",
            "- Os modelos usados sao conversoes int8 da comunidade para ONNX "
            "(`onnx-community/bge-m3-ONNX` e `onnx-community/bge-reranker-v2-m3-ONNX`), "
            "com os pesos BAAI e o `sparse_linear.pt` oficial.",
            "- A avaliacao usa top-N 5 para calcular Recall@5; a producao entrega top-N 4 ao Qwen.",
            "- Latencia de CPU varia com a maquina, carga do sistema e comprimento das consultas.",
            "- O dataset cobre FEBRABAN, INSS, CLT e padroes de fraude, mas nao substitui "
            "uma avaliacao com analistas e consultas reais de producao.",
            "",
        ],
    )
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> int:
    settings = Settings()
    if settings.app_env != "local":
        raise SystemExit("eval only runs with APP_ENV=local")
    model_root = Path(settings.retrieval_model_dir)
    if not model_root.is_absolute():
        model_root = ROOT / model_root
    known_documents = {
        document.key for document in KnowledgeFileSource(ROOT / "knowledge").scan().documents
    }
    items = load_items(Path(args.eval_file), known_documents)

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
    engine = None
    try:
        print("loading models")
        await asyncio.to_thread(embedder.load)
        await asyncio.to_thread(reranker.load)
        if not embedder.status.loaded or not embedder.sparse_status.loaded:
            print(
                f"FALHA: embedder dense={embedder.status.error} "
                f"sparse={embedder.sparse_status.error}",
                file=sys.stderr,
            )
            return 1
        if not reranker.status.loaded:
            print(f"FALHA: reranker {reranker.status.error}", file=sys.stderr)
            return 1

        engine = create_async_engine(settings.database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            count = await session.scalar(
                text("SELECT count(*) FROM knowledge_hybrid_chunks"),
            )
        if not count:
            print(
                "FALHA: knowledge_hybrid_chunks esta vazio; rode make reindex-kb",
                file=sys.stderr,
            )
            return 1
        print(f"hybrid chunks: {count}")

        store = PGVectorHybridStore(factory)
        stage1 = HybridRetriever(
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
        rerank_timeout = (
            args.rerank_timeout
            if args.rerank_timeout is not None
            else settings.rerank_timeout_seconds
        )
        rerank = TwoStageRetriever(
            stage1,
            reranker=reranker,
            rerank_enabled=True,
            top_n=args.eval_k,
            timeout_seconds=rerank_timeout,
        )

        async def dense(item: EvalItem) -> list[Retrieved]:
            dense_vector = await embedder.embed((item.question,))
            chunks = await store.dense_query(
                dense_vector[0],
                limit=settings.retrieval_top_k,
                filters=KnowledgeFilter(),
            )
            return [
                Retrieved(
                    document_key=chunk.document_key,
                    content=chunk.content,
                    score=chunk.score,
                )
                for chunk in chunks
            ]

        async def hybrid(item: EvalItem) -> list[Retrieved]:
            result = await stage1.retrieve(
                KnowledgeQuery(
                    text=item.question,
                    limit=settings.retrieval_top_k,
                ),
            )
            return to_retrieved(list(result.passages))

        async def reranked(item: EvalItem) -> list[Retrieved]:
            result = await rerank.retrieve(
                KnowledgeQuery(
                    text=item.question,
                    limit=settings.retrieval_top_k,
                ),
            )
            return to_retrieved(list(result.passages))

        print("warmup")
        await dense(items[0])
        await hybrid(items[0])
        await reranked(items[0])

        modes = (
            ("Denso (BGE-M3)", dense),
            ("Hibrido (RRF)", hybrid),
            ("Hibrido + rerank", reranked),
        )
        runs: list[ModeRun] = []
        hybrid_by_id: dict[str, list[str]] = {}
        reranked_by_id: dict[str, list[str]] = {}
        hybrid_scores: dict[str, float] = {}
        rerank_scores: dict[str, float] = {}
        hybrid_content: dict[str, str] = {}
        rerank_content: dict[str, str] = {}
        for name, function in modes:
            run_result = ModeRun(
                name=name,
                recalls=[],
                rrs=[],
                latencies_ms=[],
                per_query=[],
                corrections=[],
            )
            print(f"running {name}")
            for item in items:
                started = perf_counter()
                retrieved = await function(item)
                latency_ms = (perf_counter() - started) * 1000.0
                recall, reciprocal_rank, documents = score_result(
                    item,
                    retrieved,
                    args.eval_k,
                )
                run_result.recalls.append(recall)
                run_result.rrs.append(reciprocal_rank)
                run_result.latencies_ms.append(latency_ms)
                run_result.per_query.append(
                    {
                        "id": item.id,
                        "documents": documents[: args.eval_k],
                        "recall": recall,
                        "rr": reciprocal_rank,
                        "latency_ms": latency_ms,
                    },
                )
                if name == "Hibrido (RRF)":
                    hybrid_by_id[item.id] = documents[: args.eval_k]
                    hybrid_scores[item.id] = retrieved[0].score if retrieved else 0.0
                    hybrid_content[item.id] = retrieved[0].content if retrieved else ""
                elif name == "Hibrido + rerank":
                    reranked_by_id[item.id] = documents[: args.eval_k]
                    rerank_scores[item.id] = retrieved[0].score if retrieved else 0.0
                    rerank_content[item.id] = retrieved[0].content if retrieved else ""
            runs.append(run_result)

        corrections: list[dict[str, object]] = []
        for item in items:
            before_docs = hybrid_by_id.get(item.id, [])
            after_docs = reranked_by_id.get(item.id, [])
            before_rank = first_expected_rank(item, before_docs)
            after_rank = first_expected_rank(item, after_docs)
            before_top = before_docs[0] if before_docs else ""
            after_top = after_docs[0] if after_docs else ""
            if not after_rank:
                continue
            top_changed_to_expected = (
                after_top in item.expected_documents and before_top not in item.expected_documents
            )
            improved = before_rank is None or after_rank < before_rank or top_changed_to_expected
            if not improved:
                continue
            corrections.append(
                {
                    "id": item.id,
                    "language": item.language,
                    "question": item.question,
                    "expected_documents": item.expected_documents,
                    "before_document": before_top,
                    "before_rank": before_rank,
                    "before_score": hybrid_scores.get(item.id, 0.0),
                    "after_document": after_top,
                    "after_rank": after_rank,
                    "after_score": rerank_scores.get(item.id, 0.0),
                    "before_snippet": clean_text(
                        hybrid_content.get(item.id, ""),
                    )[:300],
                    "after_snippet": clean_text(
                        rerank_content.get(item.id, ""),
                    )[:300],
                },
            )
        corrections.sort(
            key=lambda item: (
                0 if item["after_rank"] == 1 and item["before_rank"] != 1 else 1,
                item["after_rank"] or 99,
            ),
        )

        examples = corrections[:3]
        for run_result in runs:
            if run_result.name == "Hibrido + rerank":
                run_result.corrections = corrections
        try:
            display_model_dir = model_root.relative_to(ROOT)
        except ValueError:
            display_model_dir = model_root.name
        markdown = build_result_markdown(
            items=items,
            runs=runs,
            examples=examples,
            settings=settings,
            model_dir=display_model_dir,
            backend=args.backend,
            rerank_timeout=rerank_timeout,
        )
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(output.write_text, markdown, encoding="utf-8")
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "dataset_size": len(items),
            "top_k": settings.retrieval_top_k,
            "eval_k": args.eval_k,
            "rerank_top_n_for_eval": args.eval_k,
            "backend": args.backend,
            "model_dir": str(display_model_dir),
            "modes": {run_result.name: run_result.summary() for run_result in runs},
            "corrections": corrections,
        }
        json_output = Path(args.json_output)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            json_output.write_text,
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for run_result in runs:
            summary = run_result.summary()
            print(
                f"{run_result.name}: recall@5={summary['recall_at_5']:.4f} "
                f"mrr={summary['mrr']:.4f} p50={summary['p50_ms']:.2f}ms "
                f"p95={summary['p95_ms']:.2f}ms",
            )
        print(f"results written to {output} and {json_output}")
        return 0
    finally:
        await embedder.aclose()
        await reranker.aclose()
        if engine is not None:
            await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Avalia retrieval denso, hibrido e hibrido com rerank em CPU.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / ".env.example",
    )
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
        default=ROOT / "eval" / "results.json",
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
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
