# SPEC 0014: Mensageria (RabbitMQ/Celery) e API de analises

## Objetivo
Processar analises em segundo plano e expor a API REST de analises (boleto e contracheque), com retry, descarte seguro, concorrencia controlada, idempotencia e leitura por dono. Recibos e vencimentos (P14) e entrega de notificacoes (P15) ficam fora.

## Modelo de execucao
- API recebe o upload e cria `documents` + `analyses` em estado `queued`; responde `202` com o id.
- Worker Celery consome `analysis`, reivindica a analise e executa o grafo da P11 pela ponte async dedicada.
- Ao terminar, grava relatorio, status, evento de transicao e notificacao (outbox) na MESMA transacao. Depois do commit, publica a notificacao na fila `notifications` (a entrega real e P15).
- GETs leem PostgreSQL; o relatorio completo e lido do bucket sob demanda no detalhe.

## Maquina de estados
```
queued --claim--> processing --ok--> completed
                                   \--> degraded (completed com flags de degradacao; heranca P11)
         processing --erro final--> failed
```
- `completed`/`degraded`/`failed` sao terminais. Reentrega ou transicao terminal repetida e no-op: nao duplica evento, notificacao ou relatorio.
- `claim` e atomico e idempotente: permite `queued` ou `processing` com o mesmo `task_id` (retry/reentrega) ou `processing` com lease expirado (worker morto). Duas entregas concorrentes com task ids diferentes: a segunda nao reivindica.
- `task_id` e `processing_started_at` ficam em `analyses` para auditoria e recuperacao.
- Cada transicao grava seu evento em `analysis_events` na mesma transacao (`queued`, `processing`, `completed`, `failed`). Eventos por no durante o processamento tambem sao gravados na mesma transacao do `update_state`.

## Filas, retry e descarte
- Broker RabbitMQ; backend de resultado Redis (DB separado).
- Filas: `analysis` (pesada, prefetch 1), `notifications` (leve) e `scheduler` (beat).
- `acks_late=True`, `worker_prefetch_multiplier=1`, `task_reject_on_worker_lost=True`.
- `task_time_limit`/`task_soft_time_limit` configuraveis (default 960/900s).
- `run_analysis`: maximo de 3 retries, backoff exponencial com jitter (`retry_backoff=True`, `retry_jitter=True`). Erros nao recuperaveis (documento ausente/nao suportado) falham na hora.
- Falha final marca `failed` com `error_code` seguro (sem PII/texto) e o evento `failed`; a mensagem e rejeitada para a DLQ (`task_acks_on_failure_or_timeout=False`).
- DLX `paysentineliq.dlx` roteia mensagens rejeitadas/expiradas de cada fila para `*.dlq` (`analysis.dlq`, `notifications.dlq`, `scheduler.dlq`).
- Descarte: mensagem malformada ou de analise inexistente e rejeitada sem reexecucao; nunca cria analise nova.
- Beat: `scheduler.sweep_stale_analyses` a cada 5 min marca `processing` com lease vencido como `failed` (`analysis_stale`) e grava evento na mesma transacao. Recuperacao automatica fica para a P16.

## Ponte async e banco no worker
- Tarefa Celery e sincrona; chama o caso de uso async por `run_async` com loop novo dedicado por tarefa, encerrando pending tasks/async gens e fechando o loop.
- O worker cria engine/sessao por tarefa com `NullPool` e dispose no fim; sem pool/loop compartilhado entre tarefas.
- API continua com pool async normal.

## Idempotencia e cota
- `Idempotency-Key` opcional no POST: 8..128 chars `[A-Za-z0-9._:-]`.
- Chave unica por `(owner_id, idempotency_key)`; `idempotency_request_hash = sha256(kind + ":" + sha256(file))`.
- Mesma chave + mesmo hash devolve o mesmo id (202). Mesma chave + arquivo/tipo diferente -> `409 idempotency_conflict`.
- Cota de analises simultaneas por usuario (`ANALYSIS_MAX_CONCURRENT_PER_USER`, default 2) conta `queued` + `processing`. Checagem e insercao serializadas por advisory lock por usuario; excedeu -> `429 analysis_quota_exceeded`.
- Criacao em uma transacao: lock de idempotencia (quando houver), lock de cota, rechecagem de idempotencia, contagem ativa, `documents`, `analyses`, evento `queued` e commit. O upload ao bucket ocorre antes; em conflito/erro o objeto e compensado.

## Contrato REST (autenticado; dono sempre do JWT)
### POST /api/v1/analyses
`multipart/form-data`: `kind=boleto|payslip`, `file`, header opcional `Idempotency-Key`.
- `202 {"analysis_id": "<uuid>", "status": "queued"}`.
- Erros problem+json: 401, 413, 422 (documento/chave), 429 (cota/rate limit), 503 (broker/storage indisponivel).

### GET /api/v1/analyses/{id}
- Dono diferente ou id inexistente -> `404 analysis_not_found` (anti-IDOR).
- Retorna `status`, `score`, `band`, `base_score`, `llm_adjustment`, `evidence`, `justification`, `inconsistencies`, `degradation_flags`, `created_at`, `updated_at`, `error_code` (quando houver).
- `queued`/`processing`: resultado nulo. `completed`/`degraded`: relatorio lido do bucket. `failed`: causa segura.
- Falha de leitura do bucket nao vaza detalhe: `200` com `result_available=false` e o status; log sem PII.

### GET /api/v1/analyses
- `limit` 1..50 (default 20), `cursor` opaco (created_at + id, base64url).
- Ordem `created_at DESC, id DESC`; filtro obrigatorio por `owner_id`; uma unica query (sem N+1) e sem carregar relatorio/eventos.
- Retorna `items` e `next_cursor`.

## Notificacao (outbox)
- Tabela `notifications`: id, owner_id, analysis_id, type (`analysis_completed`), payload minimo (`analysis_id`, `document_type`, `status`, `score`, `band`), status `pending`, timestamps. Sem nome, documento, CPF/CNPJ ou texto.
- Insert na mesma transacao do `complete` + evento. Apos o commit, o worker publica `notifications.dispatch_notification` com o id.
- A tarefa de notificacao e um placeholder sem entrega (P15); a publicacao apos o commit e a garantia testada nesta fase.

## Criterios de aceite (viram testes)
1. App Celery: broker/backend, filas, routing, prefetch 1, acks_late, time limits, DLX/retry e modo eager para teste unitario.
2. `claim` idempotente: primeira entrega processa; reentrega concorrente nao duplica; retry com mesmo task id continua; lease vencido recupera.
3. Criacao: 202, idempotencia (mesmo id / 409), cota 429 e IDOR.
4. GET detalhe retorna score/classe/evidencias/justificativa e esconde analise de outro dono.
5. Lista paginada por cursor, ordenada, sem N+1.
6. Sucesso grava `completed` + evento + notificacao na mesma transacao; publicacao so depois do commit.
7. Falha final grava `failed` + `error_code` seguro + evento na mesma transacao.
8. Worker usa loop dedicado e engine `NullPool`.
9. RabbitMQ real (docker): publica/consome `analysis` e declara DLQ.
10. Testes unitarios usam dispatcher fake/eager; Docker usa broker real.

## Configuracao
`RABBITMQ_URL`, `CELERY_RESULT_BACKEND`, `CELERY_TASK_ALWAYS_EAGER`, `CELERY_TASK_SOFT_TIME_LIMIT_SECONDS`, `CELERY_TASK_TIME_LIMIT_SECONDS`, `CELERY_TASK_MAX_RETRIES`, `ANALYSIS_MAX_CONCURRENT_PER_USER`, `ANALYSIS_LEASE_SECONDS`, `ANALYSIS_STALE_SWEEP_SECONDS`, `FRAUD_MODEL_DIR`, `LLM_INTERPRETER`.

## Riscos e NAO VALIDADO
- **NAO VALIDADO**: throughput/carga real do worker, DLQ em producao, RabbitMQ em cluster, beat com multiplas instancias e exactly-once (o modelo e at-least-once + idempotencia).
- **NAO VALIDADO**: recuperacao automatica de analises stale (P16); aqui o sweeper apenas falha com causa segura.
- **NAO VALIDADO**: entrega de notificacao (P15); nesta fase so o outbox e a publicacao pos-commit.
- Broker/Redis indisponiveis no POST: a analise pode ficar `queued` sem mensagem; a P16 deve varrer/reenfileirar. A API responde erro seguro quando a publicacao falha.
- A imagem do worker executa PaddleOCR; OCR real dentro do container continua NAO VALIDADO.
- Nao ha garantia de ordem entre analises; a cota e por usuario e o score e deterministico.
