# SentinelPay

SentinelPay is a portfolio-grade fraud-risk service for Brazilian financial documents. It accepts a boleto, a payslip or a utility bill, extracts the relevant fields, applies deterministic rules, fuses the result with an ML model and visual signals, optionally retrieves supporting knowledge and asks a local Qwen model for an explanation, then returns:

- a risk score from 0 to 100;
- a risk band: `low`, `attention` or `high`;
- the rules that fired, with severity and weight;
- a short justification and a list of inconsistencies;
- extracted fields and degradation flags.

The score is an estimate. It is not proof of fraud, financial advice or a legal compliance certification.

## Pipeline

```mermaid
flowchart LR
    A[PDF or image upload] --> B[Validation and OCR]
    B --> C[Document classifier]
    C --> D[Deterministic rules<br/>FEBRABAN, payslip, receipt]
    D --> E[ML model and visual signals]
    E --> F[Knowledge retrieval<br/>BGE-M3 and reranker]
    F --> G[Qwen interpretation<br/>LangGraph or CrewAI]
    G --> H[Input and output guardrails<br/>LLM judge]
    H --> I[Report<br/>score, band, evidence, justification]
    I --> J[Langfuse trace<br/>OTel metrics and logs]
```

The pipeline is designed to degrade instead of failing when an optional dependency is unavailable. An analysis can finish with `status=degraded` and a flag such as `llm_unavailable`, `rag_unavailable` or `ml_unavailable`. The deterministic rules still produce a score.

## Architecture

SentinelPay follows a hexagonal architecture. Dependencies point inward:

| Layer | Responsibility | Examples |
| --- | --- | --- |
| `domain` | Pure business rules, entities and ports. No FastAPI, SQLAlchemy or SDK imports. | FEBRABAN rules, payslip rules, risk bands, `ObservabilityTracer` port |
| `application` | Use cases, commands, queries and orchestration contracts. | Upload, create analysis, retrieval, scoring, guardrails |
| `infrastructure` | Adapters for the outside world. | PostgreSQL/pgvector, S3, PyMuPDF/PaddleOCR, ONNX models, Langfuse, OTel, Celery |
| `interface` | FastAPI routes, dependencies, request and response schemas. | `/api/v1/analyses`, `/api/v1/documents`, `/health` |
| `frontend` | Optional Next.js client and BFF. | Dashboard, login, document pages |

The backend package is `paysentineliq`, a legacy name kept for compatibility. The product name in this README is SentinelPay.

Import-linter contracts enforce the layer boundaries. See [ADR 0001](docs/adr/0001-stack-e-arquitetura.md) and the [ADR index](docs/adr/README.md).

## Stack

- Python 3.11, FastAPI, Pydantic v2 and SQLAlchemy 2.
- PostgreSQL 16 with pgvector, Alembic migrations.
- Celery, RabbitMQ and Redis for asynchronous analysis and progress events.
- MinIO (S3-compatible) for local object storage.
- PyMuPDF and PaddleOCR for native PDF text and OCR.
- BGE-M3 for dense and sparse retrieval, `bge-reranker-v2-m3` for reranking, ONNX int8 on CPU.
- Qwen through an OpenAI-compatible endpoint, with LangGraph and optional CrewAI.
- Langfuse Cloud for LLM observability, with centralized masking before every payload.
- OpenTelemetry, Prometheus, Grafana and Tempo for platform observability.
- Next.js App Router, TypeScript strict and Tailwind for the optional frontend.

## Quick start

### Prerequisites

- Docker Desktop with Compose v2.
- GNU Make, or run the underlying commands manually on Windows.
- Python 3.11 and Poetry for host-side scripts and tests.
- Optional: LM Studio with an instruction-tuned Qwen model for LLM explanations.
- Optional: Node.js and npm for the frontend.

The repository ships `.env.example` with local-only defaults. Docker Compose in this repository reads `.env.example`; do not put production credentials in it. Never commit a real `.env`.

### 1. Start the local stack

```bash
make up
make migrate
```

`make up` builds the API image if needed and waits for the health checks. `make migrate` writes a local `pg_dump` backup and applies Alembic migrations. The API is available at `http://localhost:8000`; its OpenAPI UI is at `http://localhost:8000/docs`.

```bash
curl -sS http://localhost:8000/health
```

`/health` also reports whether the retrieval models are loaded. A null or `loaded=false` model block does not stop the API, but retrieval will degrade.

### 2. Optional: connect LM Studio

Load an instruction-tuned Qwen model in LM Studio and start its OpenAI-compatible server on port 1234. Tell Compose to use the host address:

```bash
export LLM_BASE_URL=http://host.docker.internal:1234/v1
export LLM_MODEL=<model-id-shown-by-lm-studio>
make up
```

PowerShell:

```powershell
$env:LLM_BASE_URL = "http://host.docker.internal:1234/v1"
$env:LLM_MODEL = "<model-id-shown-by-lm-studio>"
make up
```

On Linux, `host.docker.internal` may not resolve. Point `LLM_BASE_URL` to an address reachable from the container, such as the Docker bridge gateway. Without LM Studio, the demo still runs and finishes as `degraded` with `llm_unavailable`.

### 3. Generate the synthetic demo

```bash
make seed-demo
```

This creates five PDFs in `demo/`, a `manifest.json` with expected bands, a local user `demo@sentinelpay.local`, and a short-lived JWT in `demo/.demo_token`. The token is signed with the local `JWT_SECRET` from `.env.example` and is not a production credential. The `demo/` directory is ignored by git.

The demo documents contain only synthetic names, CPF/CNPJ values and amounts:

| File | API `kind` | Scenario | Expected band | Deterministic subscore |
| --- | --- | --- | --- | --- |
| `boleto_valid.pdf` | `boleto` | Coherent line, barcode and amount | `low` | 0 |
| `boleto_tampered.pdf` | `boleto` | Changed check digit in the digitable line | `high` | 80 |
| `payslip_valid.pdf` | `payslip` | Coherent earnings, deductions and net pay | `low` | 0 |
| `payslip_tampered.pdf` | `payslip` | Net pay higher than total earnings | `high` | 80 |
| `utility_attention.pdf` | `receipt` | Utility bill missing amount and due date | `attention` | 50 |

The deterministic subscore is the rule layer only. The full API score also includes the ML model and visual signals, so it can be higher than the subscore. A reference run on 2026-11-18, with LM Studio unavailable, produced `13` low, `83` high, `11` low, `82` high and `65` attention. Treat the bands as the stable expectation and the exact scores as a local reference.

### 4. Run the API demo

A presenter script with timing and talking points is in [docs/demo/ROTEIRO.md](docs/demo/ROTEIRO.md).

```bash
export BASE=http://localhost:8000/api/v1
export TOKEN=$(cat demo/.demo_token)

curl -sS -X POST "$BASE/analyses" \
  -H "Authorization: Bearer $TOKEN" \
  -F "kind=boleto" \
  -F "file=@demo/boleto_tampered.pdf;type=application/pdf"
```

The response is `202 Accepted` with an `analysis_id` and `status=queued`. Poll the result:

```bash
curl -sS "$BASE/analyses/<analysis_id>" \
  -H "Authorization: Bearer $TOKEN"
```

The result contains `score`, `band`, `evidence`, `justification`, `inconsistencies` and `degradation_flags`. To watch progress as Server-Sent Events:

```bash
curl -N "$BASE/analyses/<analysis_id>/events" \
  -H "Authorization: Bearer $TOKEN"
```

Windows users can run the same `curl.exe` commands from PowerShell. If the token expires, run `make seed-demo` again.

## Tests

```bash
make install
make check
```

`make check` runs Ruff, formatting, mypy, import-linter, the non-Docker test suite with a coverage floor, and the Compose config validation. The suite covers unit tests, guarded integration tests and contract tests.

Optional and longer:

```bash
make test-docker          # rebuilds the stack and runs Docker integration tests
make eval-retrieval       # runs the 30-question retrieval evaluation
make benchmark-rerank     # measures rerank latency across K, max_length and int8/fp32
```

The `make test-docker`, `make eval-retrieval` and `make benchmark-rerank` targets were not re-run during the P19 documentation pass. Their previous results are in `eval/RESULTS.md` and in the progress log.

## Retrieval evaluation

The public dataset has 30 questions and 21 knowledge documents. It is small and synthetic; the numbers below are indicative, not production performance.

| Mode | Recall@5 | MRR | Top1 | p50 latency |
| --- | --- | --- | --- | --- |
| Dense BGE-M3 | 0.9333 | 0.8917 | 0.8333 | 134.65 ms |
| Dense + rerank | 0.9667 | 0.9611 | 0.9333 | 14586.85 ms |
| Hybrid RRF | 0.8667 | 0.8011 | 0.7333 | 135.95 ms |
| Hybrid RRF + rerank | 0.9667 | 0.9417 | 0.9000 | 14411.64 ms |

The same four configurations are published as comparable Langfuse experiments. See [eval/RESULTS.md](eval/RESULTS.md), [ADR 0025](docs/adr/0025-bi-encoder-cross-encoder.md) and [docs/observability-langfuse.md](docs/observability-langfuse.md).

## Repository layout

```text
backend/
  src/paysentineliq/
    domain/            rules, entities and ports
    application/       use cases, commands and queries
    infrastructure/    database, storage, OCR, ML, retrieval, observability
    interface/         FastAPI routes and schemas
  tests/               unit, integration and contract tests
frontend/              optional Next.js client and BFF
knowledge/             public source documents used by RAG
models/                local model assets, ignored by git
scripts/               operations, evaluation and demo scripts
eval/                  retrieval dataset and results
docs/                  ADRs, specs, agent notes and API snapshot
infra/                 local observability and database configuration
```

## API contract

The exported contract is [docs/api/openapi.json](docs/api/openapi.json). It is byte-identical to [backend/tests/contracts/openapi.json](backend/tests/contracts/openapi.json) as of 2026-11-18. Regenerate it with:

```bash
make openapi-docs
```

A contract test fails if the documentation snapshot and the test snapshot diverge.

## Production deployment

The backend image is built from `backend/Dockerfile` with the repository root as build context. The container runs `uvicorn paysentineliq.interface.api.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=* --no-access-log`. On Railway, target the container port `8000`, or override the start command with `--port $PORT`.

Required variables outside `APP_ENV=local`:

| Variable | Format | Notes |
| --- | --- | --- |
| `APP_ENV` | `production` | Any value other than `local` enables strict validation. |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/db` | Required. |
| `REDIS_URL` | `redis://host:6379/0` | Required. |
| `RABBITMQ_URL` | `amqp://user:pass@host:5672//` | Required. |
| `CELERY_RESULT_BACKEND` | `redis://host:6379/1` | Required. |
| `JWT_SECRET` | 32 or more random characters | Required. `JWT_SECRET_KEY` is accepted as an alias. |
| `S3_BUCKET` | bucket name | Required. |
| `S3_ACCESS_KEY_ID` | access key | Required. |
| `S3_SECRET_ACCESS_KEY` | secret key | Required. |
| `FRONTEND_URL` | `https://sentinelpay1.vercel.app` | Required. Exact origin, no trailing slash. |
| `CORS_ALLOWED_ORIGINS` | `https://sentinelpay1.vercel.app` | Exact origin, never `*`. |
| `ALLOWED_HOSTS` | `sentinelpay.up.railway.app,localhost,127.0.0.1` | Include the public API host. |
| `METRICS_TOKEN` | random string or empty | Empty keeps `/metrics` returning 401. |

Google sign-in variables, optional for boot:

| Variable | Format | Notes |
| --- | --- | --- |
| `GOOGLE_CLIENT_ID` | `xxxx.apps.googleusercontent.com` | Missing disables Google sign-in only. |
| `GOOGLE_CLIENT_SECRET` | Google client secret | Never commit or log it. |
| `GOOGLE_REDIRECT_URI` | `https://sentinelpay.up.railway.app/api/v1/auth/google/callback` | Must match the Google Console authorized redirect URI exactly. |
| `AUTH_LOGIN_TICKET_TTL_SECONDS` | `60` | Lifetime of the one-time login ticket. |

When Google credentials are missing, invalid or point to a different callback path, the app still boots. It logs one `google_oidc_not_configured` warning with the missing variable names, `GET /api/v1/auth/capabilities` reports `google_enabled=false`, and only `/api/v1/auth/google/login` and `/api/v1/auth/google/callback` return `503 auth_not_configured`.

The callback path in code is `/api/v1/auth/google/callback`. The older `/api/auth/google/callback` path does not exist in this service, so the Google Console entry must use the `/api/v1` prefix.

## Key decisions

The full index is in [docs/adr/README.md](docs/adr/README.md). The decisions that matter most for this project:

- [ADR 0001](docs/adr/0001-stack-e-arquitetura.md): hexagonal architecture and the base stack.
- [ADR 0002](docs/adr/0002-score-deterministico.md): the deterministic score is the source of truth; ML and LLM adjust within bounds.
- [ADR 0010](docs/adr/0010-boletos-febraban.md): FEBRABAN boleto rules.
- [ADR 0012](docs/adr/0012-contracheques.md): payslip rules driven by regulatory tables.
- [ADR 0016](docs/adr/0016-guardrails.md): four guardrail layers against prompt injection and unsafe output.
- [ADR 0025](docs/adr/0025-bi-encoder-cross-encoder.md): BGE-M3 and reranker trade-offs on CPU.
- [ADR 0027](docs/adr/0027-langfuse-observability.md): Langfuse with masking before export.
- [ADR 0028](docs/adr/0028-langfuse-pipeline-traces.md): one trace per analysis and Langfuse experiments.

## Security and privacy

- Access tokens are short-lived JWTs; refresh tokens rotate and are stored hashed. The frontend uses an HttpOnly BFF session.
- Uploads are limited by size and content type, checked by magic bytes, stored in S3 with encryption and returned through short-lived signed URLs.
- The LLM and reranker clients use an SSRF guard and a configurable allowlist.
- Before LLM prompts, CPF, CNPJ, e-mail, phone and common secrets are masked by the document redaction layer. Names and amounts can still reach the local LLM as part of the document excerpt; the LLM endpoint is local by default.
- Before every Langfuse payload, the central masker additionally covers names, amounts, boleto lines, barcodes, PIX keys, CEP and addresses.
- Raw OCR text and images are never sent to Langfuse. Free text is sent only as SHA-256 plus length; user identifiers are HMAC-SHA256.
- Secrets live in environment variables or a local ignored `.env`. `.env.example` contains placeholders only.
- The repository contains no real customer documents.

These are engineering controls. They are not a claim of LGPD, FEBRABAN or any other legal or regulatory certification.

## Limitations and honesty

1. **The score is an estimate.** It is not proof that a document is fraudulent, nor proof that it is legitimate. It is not financial or legal advice.
2. **The data is synthetic.** The demo documents, the 30-question retrieval dataset and the tests contain no real customer data. The retrieval metrics are small-sample, synthetic and indicative.
3. **The regulatory tables are not verified.** The INSS, IRRF, minimum wage and CLT files under `backend/src/paysentineliq/domain/payslip/data/regulatory/` are empty and marked `NAO VERIFICAVEL`. Payslip rules that depend on those tables are not validated against current law. `make seed-demo` uses synthetic tables only to compute expected demo bands.
4. **No real LLM was validated in the final demo run.** LM Studio was unavailable, so the API finished with `status=degraded` and `llm_unavailable`. The deterministic score, evidence and bands were produced; the Qwen justification and LLM judge were not.
5. **OCR was not exercised by the demo.** The demo PDFs contain a native text layer. Scanned-image OCR, PaddleOCR quality and visual-signal accuracy were not revalidated in P19.
6. **Some retrieval adapters are not validated.** The remote reranker, Pinecone 1024-dimension `dotproduct` deployment, PyTorch fallback and official int8 conversion by `warmup_models.py` remain unvalidated. The local ONNX int8 path and the four retrieval configurations above were validated.
7. **A real full-analysis trace in Langfuse Cloud is not validated.** Langfuse experiments are visible and validated; the complete OCR-to-judge trace with a real LLM was validated only with a fake client and a fake tracer in tests.
8. **The frontend was not exercised in P19.** The API demo is the supported path in this README. The Next.js app is optional and documented in [frontend/README.md](frontend/README.md).
9. **`make test-docker` was not re-run in P19.** The local stack, migrations, synthetic demo and five API analyses were validated. The Docker integration suite is available for a deeper run.
10. **No production performance or capacity claim.** Latencies are local CPU measurements on this machine and vary with hardware, load, prompt length and top-K.
11. **No legal or regulatory compliance claim.** The guardrails, masking and audit logs are engineering measures, not certification.
12. **The demo is not a live bill.** Synthetic boleto dates use the documented FEBRABAN factor range, which is capped at 9999 in the current data. The demo is a pipeline exercise, not a payable document.

## What was not validated

- A real analysis with Qwen, LM Studio, worker, S3 and PostgreSQL all active at the same time.
- Real OCR of scanned images and visual tamper signals.
- Remote reranker, Pinecone 1024 with `dotproduct`, PyTorch fallback and official int8 quantization.
- A full analysis trace in Langfuse Cloud with a real LLM.
- Frontend routes, BFF session and Playwright flows in this phase.
- `make test-docker`, load tests and capacity tests.
- Current INSS, IRRF, minimum wage and CLT values. The repository files are placeholders marked `NAO VERIFICAVEL`.

## License

No license file is included in this repository. Treat the code as portfolio source unless a license is added by the owner.
