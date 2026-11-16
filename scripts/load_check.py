import argparse
import asyncio
import json
import time
from collections import Counter

import httpx

_DEFAULT_PATH = "/api/v1/example/00000000-0000-0000-0000-000000000000"


async def run(
    *,
    base_url: str,
    path: str,
    requests: int,
    concurrency: int,
    request_timeout: float,
) -> dict[str, object]:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    statuses: Counter[int] = Counter()

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=request_timeout,
        limits=httpx.Limits(max_connections=concurrency),
    ) as client:

        async def one() -> None:
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.get(path)
                except httpx.HTTPError:
                    statuses[-1] += 1
                    return
                latencies.append((time.perf_counter() - started) * 1000)
                statuses[response.status_code] += 1

        await asyncio.gather(*[one() for _ in range(requests)])

    ordered = sorted(latencies)
    summary: dict[str, object] = {
        "base_url": base_url,
        "path": path,
        "requests": requests,
        "concurrency": concurrency,
        "status_counts": {str(code): count for code, count in sorted(statuses.items())},
        "responses": len(latencies),
        "latency_ms": {
            "min": round(ordered[0], 2) if ordered else None,
            "p50": round(_percentile(ordered, 50), 2) if ordered else None,
            "p95": round(_percentile(ordered, 95), 2) if ordered else None,
            "max": round(ordered[-1], 2) if ordered else None,
        },
        "rate_limited": statuses.get(429, 0),
        "transport_errors": statuses.get(-1, 0),
        "server_errors": sum(count for code, count in statuses.items() if 500 <= code <= 599),
    }
    return summary


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    index = min(len(values) - 1, round((percentile / 100) * (len(values) - 1)))
    return values[index]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Smoke test de concorrencia contra a API local. Valida a presenca de 429 "
            "(token bucket) e mede latencia basica; nao e benchmark de producao."
        ),
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--path", default=_DEFAULT_PATH)
    parser.add_argument("--requests", type=int, default=120)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    if args.requests <= 0 or args.concurrency <= 0:
        parser.error("requests e concurrency devem ser positivos")

    summary = asyncio.run(
        run(
            base_url=args.url,
            path=args.path,
            requests=args.requests,
            concurrency=args.concurrency,
            request_timeout=args.timeout,
        ),
    )
    print(json.dumps(summary, indent=2))

    if summary["transport_errors"] or summary["server_errors"]:
        print("FALHA: houve erro de transporte ou 5xx; veja os contadores acima.")
        return 1
    if summary["rate_limited"] == 0:
        print(
            "FALHA: nenhum 429 observado. Verifique se o Redis esta no ar, se o caminho "
            "passa pelo RateLimitMiddleware e se o bucket ja esta cheio; aumente --requests.",
        )
        return 1
    print("OK: token bucket respondeu com 429 dentro da concorrencia testada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
