# SentinelPay demo script

Target audience: recruiter, hiring manager or engineer reviewing the project.

Duration: 8 to 12 minutes.

## Before the call

Run these commands once and keep the terminal open:

```bash
make up
make migrate
make seed-demo
```

Check the API and the loaded models:

```bash
curl -sS http://localhost:8000/health
```

Open `demo/manifest.json` and the five PDFs in `demo/`. Keep `README.md` and the Mermaid pipeline diagram visible.

Optional: if a terminal is not convenient, open `http://localhost:8000/docs` for the API contract.

## 1. Frame the project (1 minute)

Say:

> SentinelPay is a fraud-risk service for Brazilian boletos, payslips and utility bills. It returns a 0 to 100 score, a risk band, the rules that fired, extracted fields and a short explanation. The deterministic rules are the source of truth; ML, retrieval and the LLM are bounded adjustments.

Show the pipeline diagram in `README.md` and point to the hexagonal layers. Mention that the domain has no FastAPI, SQLAlchemy or Langfuse imports; those are adapters behind ports.

## 2. Show the synthetic data boundary (1 minute)

Open `demo/manifest.json`. Show:

- `synthetic: true`;
- the five files and the expected bands;
- the deterministic subscore for each file.

Say:

> Everything in this demo is synthetic. The repository contains no customer documents. The demo user and token are local and short-lived.

Do not show or copy the token value on screen. It is a local JWT, but there is no reason to expose it.

## 3. Authenticate the API (1 minute)

```bash
export BASE=http://localhost:8000/api/v1
export TOKEN=$(cat demo/.demo_token)
```

On PowerShell:

```powershell
$env:BASE = "http://localhost:8000/api/v1"
$env:TOKEN = Get-Content demo/.demo_token -Raw
```

Explain that the demo bypasses Google OIDC only for local reproducibility. In the full application, the browser uses an HttpOnly BFF session with short-lived access tokens and rotating refresh tokens.

## 4. Start with a valid boleto (1 minute)

```bash
curl -sS -X POST "$BASE/analyses" \
  -H "Authorization: Bearer $TOKEN" \
  -F "kind=boleto" \
  -F "file=@demo/boleto_valid.pdf;type=application/pdf"
```

Show the `202 Accepted` response with `analysis_id` and `status=queued`. Poll:

```bash
curl -sS "$BASE/analyses/<analysis_id>" \
  -H "Authorization: Bearer $TOKEN"
```

Show:

- `band: low`;
- zero or few evidence items;
- extracted boleto fields;
- `degradation_flags` containing `llm_unavailable` if LM Studio is not running.

Say:

> The deterministic layer found no critical rules. The score is still an estimate, not a guarantee that the document is legitimate.

## 5. Upload the tampered boleto (2 minutes)

```bash
curl -sS -X POST "$BASE/analyses" \
  -H "Authorization: Bearer $TOKEN" \
  -F "kind=boleto" \
  -F "file=@demo/boleto_tampered.pdf;type=application/pdf"
```

Poll again. Show:

- `band: high`;
- the evidence item for the invalid check digit;
- the justification, or the degraded template if the LLM is unavailable.

Say:

> The line is internally inconsistent. This is a deterministic rule, not a model guess. The ML and LLM can adjust the score, but they cannot hide a critical floor.

## 6. Show the payslip pair (2 minutes)

Run the same flow for `payslip_valid.pdf` and `payslip_tampered.pdf`:

```bash
curl -sS -X POST "$BASE/analyses" \
  -H "Authorization: Bearer $TOKEN" \
  -F "kind=payslip" \
  -F "file=@demo/payslip_tampered.pdf;type=application/pdf"
```

Show the low band for the valid file and the high band for the net-above-earnings case. Point out that the payslip regulatory tables in the repository are empty and marked `NAO VERIFICAVEL`, so the regulatory comparisons are a known limitation.

## 7. Show the attention band (1 minute)

```bash
curl -sS -X POST "$BASE/analyses" \
  -H "Authorization: Bearer $TOKEN" \
  -F "kind=receipt" \
  -F "file=@demo/utility_attention.pdf;type=application/pdf"
```

Show the `attention` band and the missing amount and due date evidence. This is the case that demonstrates the middle band without a critical rule.

## 8. Show progress events (optional, 1 minute)

```bash
curl -N "$BASE/analyses/<analysis_id>/events" \
  -H "Authorization: Bearer $TOKEN"
```

Explain that PostgreSQL is the source of truth for progress. The SSE endpoint sends the current snapshot and finishes with a `done` event. This is what the frontend uses instead of guessing a percentage.

## 9. Show the quality gate (1 minute)

In a separate terminal:

```bash
make check
```

Mention the gate: Ruff, formatting, mypy, import-linter, the non-Docker test suite with coverage, and Compose validation. If the command is too slow for the call, say it was already run and show the last output.

## 10. Show retrieval and observability evidence (2 minutes)

Open `eval/RESULTS.md` and `docs/observability-langfuse.md`.

Show:

- the four retrieval modes and the small-sample MRR table;
- the caveat that 30 public questions are not a production benchmark;
- the Langfuse experiment links and the masking rules.

Say:

> The hybrid RRF mode was worse than dense in this corpus. Dense plus rerank was the best quality result. Reranking costs about 14 seconds per query on CPU, so the default is a trade-off, not a free win.

## 11. Close with the limits (1 minute)

Say:

> This is a portfolio-grade engineering project, not a certified fraud detector. The score is an estimate. The data is synthetic. The regulatory tables in the repository are not verified. The demo ran in degraded mode because LM Studio was unavailable, so the Qwen explanation and the LLM judge were not exercised in the final run. A real full-analysis trace in Langfuse Cloud, real OCR of scanned documents, the remote reranker and Pinecone 1024 are still not validated.

Do not claim:

- real fraud detection accuracy;
- production latency or capacity;
- LGPD, FEBRABAN or any legal compliance;
- that the demo documents are real bills;
- that the LLM explanation was validated with a live Qwen model in this run.

## Recovery commands

If the stack is unhealthy:

```bash
docker compose --env-file .env.example ps
docker compose --env-file .env.example logs --tail=100 api worker
```

If the token expired:

```bash
make seed-demo
```

If a port is busy, check `API_PORT`, `POSTGRES_PORT` and the other published ports in `.env.example`. Do not edit `.env.example` with real credentials.
