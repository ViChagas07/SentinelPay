# ADR 0020 - Observabilidade: OTel, Tempo, Prometheus e Grafana

## Status

Aceito em 2026-11-14.

## Contexto

A API, o worker e o beat precisam ser observaveis sem acoplar o codigo a um SaaS, sem labels de
alta cardinalidade e sem vazar dados pessoais. O ambiente local ja tem Postgres, Redis,
RabbitMQ, MinIO e Mailpit; a observabilidade deve ser opcional e reproduzivel.

## Decisao

### Backend de traces

- **Grafana Tempo** como backend de traces local, recebendo OTLP pelo `otel-collector`.
  Tempo e open source, aceita OTLP nativo e integra com Grafana sem dependencia paga.
- O coletor aplica `memory_limiter`, `batch` e remocao de atributos HTTP sensiveis antes do
  Tempo. A aplicacao exporta OTLP HTTP; o destino vem exclusivamente de
  `OTEL_EXPORTER_OTLP_ENDPOINT`.
- `OTEL_SDK_DISABLED=true` desliga a instrumentacao. No Compose o endpoint padrao aponta para
  `http://otel-collector:4318`; sem o profile o exporter simplesmente nao entrega, sem afetar
  requisicoes ou tarefas.

### Metricas

- `prometheus-client` com metricas de dominio em modulo unico. A API expoe `/metrics`; o
  worker grava no mesmo `PROMETHEUS_MULTIPROC_DIR` (volume compartilhado), e o
  `MultiProcessCollector` agrega na API. Isso evita um exporter sidecar e mantem a pipeline
  visivel no mesmo endpoint.
- Alertas e dashboards sao arquivos versionados no repositorio; nada e criado manualmente na
  UI. Grafana usa datasources Prometheus/Tempo provisionados.
- `/metrics` exige token (`METRICS_TOKEN`) por Bearer ou `X-Metrics-Token`. A rede interna do
  Compose e uma segunda camada, nao a unica.

### PII

- A politica e deny-by-default: nenhum label/atributo recebe ID de usuario/documento, texto,
  corpo, query, cookie ou cabecalho de autorizacao.
- `PiiSanitizingSpanProcessor` roda antes do `BatchSpanProcessor`: redige chaves sensiveis,
  mascara PII em strings, trunca valores, limpa nomes/eventos de excecao e injeta apenas
  `request_id`.
- O coletor remove atributos HTTP sensiveis como defesa em profundidade; mesmo que uma
  instrumentacao futura adicione um campo, ele nao deve chegar ao Tempo.
- Labels Prometheus sao enums ou rotas template; a rota bruta e substituida por `unmatched`
  quando nao ha template.

### request_id

- HTTP: `RequestIdMiddleware` define o ContextVar; o middleware OTel fica por dentro dele, de
  modo que o span ja nasce com o `request_id` (ou o sanitizador o adiciona).
- Celery: o dispatcher envia `request_id` nos headers; sinais `task_prerun`/`task_postrun`
  restauram/limpam o ContextVar e adicionam o valor ao span corrente. O traceparent e
  propagado pela instrumentacao do Celery.

### Alternativas rejeitadas

- SaaS APM: custo e lock-in sem necessidade local.
- Jaeger: viavel, mas Tempo integra melhor com Grafana e usa OTLP nativo.
- Pushgateway para metricas do worker: mais um componente e perde a agregacao por processo;
  multiprocess mode resolve.
- Labels com `user_id`/`document_id`: alta cardinalidade e risco de PII, proibido.
- Instrumentar tudo manualmente sem OTel: mais codigo e sem propagacao entre FastAPI/Celery.

## Consequencias

- A observabilidade local exige o profile `observability`; sem ele a aplicacao continua
  saudavel e `/metrics` segue disponivel para scrape interno.
- O volume de traces e a retencao sao de laboratorio; producao exige decisao de sampling,
  armazenamento e HA (NAO VALIDADO).
- A sanitizacao e centralizada; qualquer nova instrumentacao deve ser coberta por teste de PII.
- O token de metricas precisa ser rotacionado em producao e compartilhado com o Prometheus.
