# ADR 0017: Celery/RabbitMQ para analises assincronas

- Status: aceito
- Data: 2026-11-14

## Contexto
A P11 entrega o grafo de analise on-demand. A P13 precisa tirar a analise do request HTTP, processar em segundo plano, sobreviver a falhas/reentregas, limitar concorrencia por usuario e expor API de consulta. O processamento e pesado (OCR/visao/LLM/RAG) e o resultado precisa ser auditavel.

## Decisao
- **Celery 5.7 + RabbitMQ** como broker e **Redis** como result backend. RabbitMQ ja esta no Compose e oferece DLX/DLQ; Redis ja e usado para cache/rate limit.
- **Filas separadas** `analysis`, `notifications`, `scheduler`. `analysis` e pesada: prefetch 1, `acks_late`, limite soft/hard, retry exponencial com jitter. `notifications` e reservada para a P15; `scheduler` para beat.
- **DLQ por fila** via `paysentineliq.dlx`; mensagens rejeitadas/expiradas vao para `*.dlq`. `task_acks_on_failure_or_timeout=False` garante que falha final seja rejeitada, nao ack silencioso.
- **Tarefa sincrona + ponte async dedicada**: cada tarefa cria um loop novo, executa o caso de uso, cancela pendentes e fecha o loop. Engine/sessao do worker usam `NullPool` e sao descartados ao fim. Isso evita reutilizar conexoes/loops entre tarefas e o classico "Future attached to a different loop".
- **At-least-once + idempotencia**: a maquina de estados usa `claim` atomico com `task_id` e lease. Reentrega concorrente nao processa; retry com o mesmo task id continua; lease vencido permite recuperacao.
- **Cota e idempotencia no banco**: advisory locks por `(owner, idempotency key)` e por `owner` serializam criacao/checagem de cota; a chave e unica em `analyses`. Nada de contador em Redis como fonte de verdade.
- **Transactional outbox**: status terminal, evento e notificacao na mesma transacao. Publicacao na fila `notifications` so depois do commit; a entrega fica para a P15.
- **GETs em `application/queries`** e POST em `application/commands`, mantendo CQRS leve. Listagem por cursor `(created_at, id)` em uma query, sem N+1.
- **Sem Flower** nesta fase (YAGNI); observabilidade fica para a P16.
- **Beat** roda `sweep_stale_analyses` para devolver `processing` com lease vencido a `queued` e republicar a tarefa, evitando `processing` eterno apos morte do worker. Limite de recuperacoes e alertas ficam para a P16.
- **`degraded` continua terminal de sucesso** (heranca P11) quando componentes opcionais falham; `failed` e reservado a falha sem resultado confiavel.

## Alternativas descartadas
- **BackgroundTasks/FastAPI**: sem retry, DLQ, concorrencia ou durabilidade.
- **RQ/arq**: menos maduro para DLX/DLQ e beat no stack atual; Celery ja e o padrao do projeto.
- **Processar no request**: bloqueia, nao escala e perde trabalho em restart.
- **Resultado no Redis como fonte de verdade**: PostgreSQL e a fonte; GETs leem o banco e o relatorio no bucket.
- **Notificacao direta no commit**: perderia o evento em falha de broker; outbox resolve.
- **Contador de cota no Redis**: diverge do banco e nao sobrevive a falhas; advisory lock no PG e simples e correto.
- **Exactly-once**: nao existe de forma barata; usamos at-least-once com idempotencia e transicoes terminais no-op.

## Consequencias
- Reentregas sao seguras; o pior caso e reprocessar uma analise cujo lease venceu, sobrescrevendo o resultado de forma consistente.
- O worker nao compartilha pool/loop, ao custo de abrir conexao por tarefa (aceitavel na escala atual).
- Uma falha do broker no POST deixa a analise `queued` sem mensagem; a P16 deve reprocessar. A API retorna erro seguro quando a publicacao falha.
- **NAO VALIDADO**: carga real, DLQ em producao, multiplas instancias de beat, recuperacao de mensagens orfas e entrega de notificacoes. O sistema nao promete exactly-once.

