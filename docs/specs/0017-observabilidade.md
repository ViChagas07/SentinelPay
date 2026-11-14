# SPEC 0017 - Observabilidade (OpenTelemetry, Prometheus e Grafana)

## Objetivo

Enxergar saude, latencia e comportamento da API e da pipeline sem expor dados pessoais.
Telemetria e opt-in local: o profile `observability` sobe collector, Tempo, Prometheus e Grafana;
a aplicacao continua funcionando sem ele.

## Escopo

- Traces OpenTelemetry para FastAPI, SQLAlchemy, Redis, httpx e Celery, com propagacao de
  `request_id` por HTTP e por headers de tarefa.
- Exportador OTLP HTTP configurado por `OTEL_EXPORTER_OTLP_ENDPOINT` (sem destino fixo).
- Metricas Prometheus em `/metrics`, protegidas por `METRICS_TOKEN` (Bearer ou `X-Metrics-Token`).
- Instrumentacao de metricas: requisicoes/latencia, 429, analises por tipo/banda, duracao por
  etapa, LLM, guardrails, profundidade de filas, notificacoes por canal/status e cache SWR.
- Profile Compose `observability` com `otel-collector`, `tempo`, `prometheus` e `grafana`.
- Datasources, dashboards e regras de alerta provisionados como codigo.

## Fora de escopo

- Producao real: so o destino OTLP e parametrizado; ambiente de producao NAO VALIDADO.
- Servico pago, SaaS de observabilidade, log aggregation, APM proprietario.
- Metricas de negocio individualizadas (por usuario/documento) ou qualquer label de alta
  cardinalidade.
- Coleta de logs estruturados no Loki (pode ser fase futura).

## Politica de PII (obrigatoria)

- Spans nunca contem CPF/CNPJ, e-mail, telefone, nome, endereco, salario, texto de documento,
  prompt, resposta do LLM, corpo de requisicao, cookies, Authorization ou query string.
- Um `SpanProcessor` sanitiza na entrada: remove/redige chaves sensiveis, mascara PII em strings,
  trunca valores, remove `http.url`/`http.target`/`url.full`/`url.query` e headers sensiveis, e
  injeta apenas `request_id` (nao e PII) quando disponivel.
- Nomes de span e descricoes de status tambem passam pelo mascaramento.
- Labels Prometheus sao apenas enums/rotas template: `method`, `route`, `status`, `scope`,
  `document_type`, `band`, `stage`, `model`, `outcome`, `layer`, `queue`, `channel`,
  `cache result`. Proibido `user_id`, `document_id`, `analysis_id`, e-mail, CPF, telefone,
  texto de documento ou URL crua.
- O coletor tambem remove atributos HTTP sensiveis como defesa em profundidade.

## Metricas

Prefixo `paysentineliq_`:

| Metrica | Tipo | Labels |
| --- | --- | --- |
| `http_requests_total` | counter | `method`, `route`, `status` |
| `http_request_duration_seconds` | histogram | `method`, `route` |
| `http_429_total` | counter | `scope` (`ip`/`user`) |
| `analyses_total` | counter | `document_type`, `band` |
| `pipeline_stage_duration_seconds` | histogram | `stage`, `document_type` |
| `llm_requests_total` | counter | `model`, `outcome` (`success`/`error`/`retry`) |
| `llm_request_duration_seconds` | histogram | `model` |
| `guardrail_blocks_total` | counter | `layer` |
| `queue_depth` | gauge | `queue` |
| `notifications_total` | counter | `channel`, `status` |
| `cache_events_total` | counter | `result` (`hit`/`miss`/`stale`/`refresh`/`error`) |

- Multiprocess: API e worker compartilham `PROMETHEUS_MULTIPROC_DIR` (volume) para que a API
  exponha tambem as metricas da pipeline; em single-process usa-se um registry proprio.
- Queue depth e atualizada por um monitor que consulta a Management API do RabbitMQ e mantem
  gauges para `analysis`, `notifications`, `scheduler` e as DLQs.
- `/metrics` retorna `text/plain; version=0.0.4` e exige token. Sem token valido: 401
  problem+json. A rota fica fora do tracing para evitar ruido.

## Tracing

- Resource: `service.name` por processo (`paysentineliq-api`, `paysentineliq-worker`,
  `paysentineliq-beat`), `service.version`, `deployment.environment`.
- Propagadores W3C TraceContext + Baggage.
- FastAPI: span de request; rota template em `http.route`; `/metrics`, `/health` e `/ready`
  excluidos.
- SQLAlchemy, Redis, httpx e Celery instrumentados. O `CeleryTaskDispatcher` envia
  `request_id` nos headers; o worker restaura o ContextVar e adiciona `request_id` ao span.
- Pipeline: spans `pipeline.<stage>` para `load`, `ingest`, `guard`, `classify`, `boleto`,
  `payslip`, `receipt`, `fraud`, `rag`, `interpret`, `persist`, mais `pipeline.run`.
- LLM: span `llm.complete` com modelo/outcome/retry_count, sem prompt/resposta.
- Exportador OTLP HTTP (`OTEL_EXPORTER_OTLP_ENDPOINT`), BatchSpanProcessor e sampler
  parent-based com ratio configuravel. `OTEL_SDK_DISABLED=true` desliga tudo.
- Sem endpoint configurado ou SDK desligado, a aplicacao nao registra exporter.

## Stack local (`--profile observability`)

- `otel-collector`: recebe OTLP gRPC/HTTP, aplica `memory_limiter`, `batch` e remove atributos
  HTTP sensiveis; exporta para `tempo`.
- `tempo`: backend de traces local (Grafana Tempo), retencao curta de laboratorio.
- `prometheus`: scrape da API em `/metrics` com Bearer token, regras de alerta e retencao local.
- `grafana`: datasources Prometheus/Tempo e dashboards provisionados por arquivos:
  API, pipeline de IA, filas/notificacoes e seguranca.
- Portas: `GRAFANA_PORT` (3001), `PROMETHEUS_PORT` (9090), `TEMPO_PORT` (3200),
  `OTEL_GRPC_PORT` (4317), `OTEL_HTTP_PORT` (4318).
- Nenhum servico pago e obrigatorio.

## Alertas basicos

- `ApiDown`: `up{job="paysentineliq-api"} == 0`.
- `HighApiErrorRate`: taxa de 5xx > 5% por 5 min.
- `AnalysisQueueBacklog`: profundidade de `analysis` > 25 por 10 min.
- `LlmUnavailable`: aumento de `llm_requests_total{outcome="error"}` em 5 min.
- `DeadLetterQueueNotEmpty`: qualquer DLQ com mensagens.

## Criterios de aceite (viram testes)

1. `/metrics` sem credencial retorna 401; com token retorna as metricas.
2. Uma analise sintetica produz `analyses_total`, `pipeline_stage_duration_seconds` e demais
   metricas nomeadas, inclusive vindas do worker via multiprocess.
3. Nenhum span exportado contem CPF/e-mail/texto de documento; nenhum label contem PII ou IDs
   de alta cardinalidade.
4. `request_id` chega ao worker e aparece no span da tarefa.
5. `docker compose --profile observability config --quiet` e valido; Grafana sobe com
   datasources e quatro dashboards provisionados.
6. Prometheus consulta dados de uma analise sintetica apos o scrape.

## Riscos e NAO VALIDADO

- Producao (OTLP real, sampling, retencao, HA do collector/Tempo/Prometheus/Grafana) NAO
  VALIDADA; apenas o destino e parametrizado.
- Volume de traces e custo de armazenamento nao foram medidos; retencao local e curta.
- Queue depth depende da Management API do RabbitMQ e de credenciais internas.
- `PROMETHEUS_MULTIPROC_DIR` acumula arquivos de processos encerrados; a limpeza/rotacao
  operacional nao foi validada.
- A sanitizacao cobre os padroes conhecidos de PII e chaves sensiveis; novos atributos de
  instrumentacoes futuras devem ser revisados.
