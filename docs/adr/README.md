# Architecture Decision Records

This index lists the decisions that shaped SentinelPay. The records are kept in Portuguese because they are part of the internal engineering history; this index is in English for recruiters and external readers.

| ADR | Decision | Status |
| --- | --- | --- |
| [0000](0000-template.md) | Template for new ADRs | Template |
| [0001](0001-stack-e-arquitetura.md) | Base stack and hexagonal architecture | Accepted |
| [0002](0002-score-deterministico.md) | Deterministic score as the source of truth | Accepted |
| [0003](0003-artefato-graphify.md) | Graphify artifact is not versioned | Accepted |
| [0004](0004-minio-local.md) | Local MinIO pinned to a community image | Accepted |
| [0005](0005-fundacao-backend.md) | Backend foundation and cross-cutting concerns | Accepted |
| [0006](0006-camadas-de-protecao.md) | Reusable protection layers | Accepted |
| [0007](0007-autenticacao.md) | Google OIDC, JWT and sessions | Accepted |
| [0008](0008-storage-s3-upload.md) | S3 storage, object keys and safe upload | Accepted |
| [0009](0009-ocr-visao.md) | OCR, PDF reading and visual signals | Accepted |
| [0010](0010-boletos-febraban.md) | Deterministic FEBRABAN boleto analysis | Accepted |
| [0011](0011-cqrs-leve.md) | Light CQRS instead of full event sourcing | Accepted |
| [0012](0012-contracheques.md) | Payslip analysis driven by regulatory tables | Accepted |
| [0013](0013-fusao-ml.md) | Deterministic, ML and visual score fusion | Accepted |
| [0014](0014-rag.md) | Deterministic RAG with PGVector and Pinecone | Accepted |
| [0015](0015-agentes-ia.md) | AI agents with LangGraph, LangChain and CrewAI | Accepted |
| [0016](0016-guardrails.md) | Four guardrail layers against prompt injection | Accepted |
| [0017](0017-mensageria.md) | Celery and RabbitMQ for asynchronous analyses | Accepted |
| [0018](0018-recibos-payables.md) | Receipts, payables and reminders | Accepted |
| [0019](0019-notificacoes.md) | Notifications, consent and pending providers | Accepted |
| [0020](0020-observabilidade.md) | OTel, Tempo, Prometheus and Grafana | Accepted |
| [0021](0021-estrategia-hardening-testes.md) | Hardening and testing strategy | Accepted |
| [0022](0022-two-stage-retrieval.md) | Two-stage retrieval with BGE-M3 and a local reranker | Accepted |
| [0023](0023-hybrid-retrieval-1024.md) | Hybrid storage and search at 1024 dimensions | Accepted |
| [0024](0024-two-stage-rerank.md) | Top-N reranking and remote adapter | Accepted |
| [0025](0025-bi-encoder-cross-encoder.md) | BGE-M3 bi-encoder and v2-m3 cross-encoder on CPU | Accepted |
| [0026](0026-progresso-sse-cancelamento.md) | Persisted progress, SSE and cooperative cancellation | Accepted |
| [0027](0027-langfuse-observability.md) | Langfuse Cloud with masking before export | Accepted |
| [0028](0028-langfuse-pipeline-traces.md) | End-to-end trace per analysis and Langfuse experiments | Accepted |

## How to add an ADR

1. Copy `0000-template.md` to the next number.
2. Describe context, decision, alternatives and consequences.
3. Add the record to this table.
4. Link the ADR from the relevant spec in `docs/specs/` and from `PROGRESS.md` when the decision closes a phase.
