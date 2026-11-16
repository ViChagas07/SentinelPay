# Auditoria de testes e cobertura (P17)

Medicao em 2026-11-16 com `pytest -m "not docker" --cov=paysentineliq`:
779 passed, 2 skipped, 41 deselected, cobertura total de 82,97% (11.207 declaracoes, 1.908
sem execucao). A suite Docker (41 testes) e medida separadamente porque depende de Postgres,
Redis, RabbitMQ, MinIO e Mailpit.

## Cobertura por camada (sem Docker)

| Camada | Cobertura | Declaracoes | Leitura |
| --- | --- | --- | --- |
| `application` | 91,1% | 1.786/1.960 | Comandos, queries, guardrails e portas bem cobertos. |
| `domain` | 91,6% | 2.782/3.036 | Regras de boleto, contracheque, recibo, score e notificacoes. |
| `infrastructure` | 73,7% | 3.749/5.087 | Repositorios, S3, Redis, SWR, ML e RAG dependem de servico externo. |
| `interface` | 87,4% | 982/1.124 | Rotas cobertas por testes de rota; wiring e lifespan ficam para Docker. |
| Total | 82,97% | 9.299/11.207 | Piso de 80% aplicado em `make coverage`. |

## Modulos sem teste direto

"Sem teste direto" significa que nenhum teste importa ou executa o modulo na suite padrao.
Nao significa necessariamente defeito: portas e entrypoints de CLI podem ser exercitados por
Makefile ou por outro teste.

| Modulo | Cobertura | Situacao |
| --- | --- | --- |
| `application/ports/antivirus.py` | 0% | Porta sem adaptador; antivirus real e pendencia declarada (P05). |
| `infrastructure/ml/train.py` | 0% | Entrypoint CLI de `make train`; o treino em `ml/training.py` e testado. |
| `infrastructure/guardrails/train.py` | 0% | Entrypoint CLI de `make train-guardrails`; o treino e testado. |
| `infrastructure/rag/ingest.py` | 0% | Entrypoint CLI de `make ingest-knowledge`; o handler e testado. |

## Modulos com cobertura baixa na suite sem Docker

| Modulo | Cobertura | Onde e coberto |
| --- | --- | --- |
| `db/repositories/payables.py` | 21,9% | `test_payables_repository.py` (Docker). |
| `db/repositories/notifications.py` | 25,3% | `test_notifications_repository.py` (Docker). |
| `cache/swr.py` | 23,3% | `test_swr_cache.py` (Redis, Docker). |
| `security/oidc_state.py` | 30,8% | `test_oidc_state.py` (Redis, Docker). |
| `storage/s3.py` | 32,4% | `test_s3_storage.py` e `test_document_upload.py` (MinIO, Docker). |
| `readiness.py` | 36,0% | `test_ready.py` (Postgres/Redis, Docker). |
| `db/repositories/analyses.py` | 36,2% | `test_analysis_repository.py` e `test_analysis_queue_repository.py` (Docker). |
| `db/repositories/users.py` | 38,7% | `test_auth_repositories.py` e `test_auth_service_db.py` (Docker). |
| `rag/pgvector.py` | 21,7% | `test_rag_pgvector.py` (PGVector, Docker). |
| `ai/crew.py` | 60,0% | Runner fake; CrewAI real NAO VALIDADO. |
| `interface/api/dependencies.py` | 63,3% | Testes de rota usam overrides; Docker E2E cobre o wiring real. |
| `interface/api/main.py` | 70,1% | Lifespan e middleware completos so no Compose (Docker). |

## Servicos externos por teste Docker

| Servico | Teste(s) |
| --- | --- |
| Postgres | repositorios, migration roundtrip, analyses, payables, notifications. |
| Redis | rate limit concorrente, SWR, revoked tokens, OIDC state, brute force. |
| RabbitMQ | `test_analysis_queue_e2e.py` (fila, DLQ, reentrega idempotente). |
| MinIO | `test_s3_storage.py`, `test_document_upload.py`, `test_document_api.py`. |
| Mailpit | `test_notifications_e2e.py` (e-mail real no Mailpit). |

## Matriz de seguranca

| Requisito | Evidencia existente | Lacuna fechada na P17 |
| --- | --- | --- |
| IDOR em rotas com dono | documento, analise, notificacao e confirm de payable | mutacoes de payable, leitura/delete de notificacao e listas cruzadas com banco real. |
| SQLi | `test_injection_docker.py` (payloads classicos e schema intacto). | nenhuma; revalidado no fechamento. |
| SSRF | `test_ssrf_guard.py` e `test_safe_http_client.py`. | nenhuma. |
| CSRF | `test_auth_routes.py` (refresh/logout sem token). | nenhuma. |
| Forca bruta | `test_bruteforce_unit.py`, `test_bruteforce.py`, rotas de auth. | nenhuma. |
| Rate limit concorrente | `test_rate_limit_concurrency.py` (20 chamadas, 5 permitidas). | script de carga local para 429 e tempos. |
| Escalada de papel | `test_auth_routes.py` (claim admin vs role do banco). | caso Docker com banco real. |
| Upload malicioso | extensao falsa e traversal no inspector/handler; PDF ativo. | bomba de descompressao e rejeicao antes de decodificar pixels. |

## Lacunas fechadas na P17

1. Piso de 80% aplicado em `make coverage` e `make check`.
2. Utilitario de contagem de queries e teste dos tres endpoints de listagem com banco real.
3. Testes Docker de IDOR em todas as rotas com dono e de escalada de papel.
4. Teste de bomba de descompressao e checagem de dimensao antes da decodificacao.
5. Teste de stampede em miss frio do SWR e script de carga local.
6. Snapshot de contrato OpenAPI.
7. Auditoria, MEMORY e PROGRESS revisados.

## NAO VALIDADO (herdado e honesto)

- Producao: AWS real, antivirus, provedores de SMS/WhatsApp, e-mail com SPF/DKIM/bounce,
  OCR pt/es real, CrewAI/LM Studio reais, Pinecone real, DDoS de borda e HA.
- Capacidade de producao: o script de carga mede apenas a API local.
- Ataques reais/adaptativos e malware real: os testes usam conteudo sintetico controlado.
- Cobertura de 80% nao prova ausencia de defeitos.

## Revalidacao final (2026-11-16)

| Verificacao | Resultado |
| --- | --- |
| `make check` | 783 passed + 2 skips + 44 deselected; cobertura 82,98% (piso 80%). |
| `make test-docker` | 43 passed + 1 skip (OCR real opt-in). |
| Postgres/Redis/RabbitMQ/MinIO/Mailpit | cobertos pela suite Docker acima. |
| Ruff + format | verdes. |
| mypy strict | 357 arquivos, sem erros. |
| import-linter | 6 contratos mantidos, 0 quebrados. |
| Bandit | 0 achados (`# nosec B105` justificado no token local de metricas). |
| pip-audit | sem vulnerabilidades conhecidas; 4 CVEs do Chroma ignorados (justificativa no Makefile). |
| `make load-check` | 60x404 + 60x429; p50 95,63 ms, p95 143,29 ms, max 155,64 ms. |

A cobertura subiu de 82,97% para 82,98% com os testes novos. O ganho pequeno e esperado: a maior
parte do codigo adicionado e de teste, e os endpoints exercitados ja tinham cobertura por outros
testes. O valor esta nos invariantes provados (query count, IDOR com banco real, contrato,
stampede e limites de upload), nao no percentual.
