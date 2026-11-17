# SPEC 0021: Reranking em dois estagios (P17.1, ETAPA C)

## Objetivo
Fechar o estagio 2 do retrieval: o `HybridRetriever` entrega top-K candidatos e o `BgeRerankerV2M3` ou `RemoteReranker` reduz para top-N antes do Qwen. A interface vista pelo LangGraph e pelo CrewAI continua sendo `RagContextPort`; agentes nao conhecem modelos, backends ou scores internos.

## Comportamento das flags
- `HYBRID_RETRIEVAL_ENABLED=false`: `KnowledgeRetriever` antigo de 8 dimensoes, sem reranking.
- `HYBRID_RETRIEVAL_ENABLED=true` e `RERANK_ENABLED=false`: `TwoStageRetriever` sem reranker, devolvendo o top-K do estagio 1 na ordem original.
- `HYBRID_RETRIEVAL_ENABLED=true` e `RERANK_ENABLED=true`: `TwoStageRetriever` reranqueia o top-K e devolve top-N.
- `RERANKER_BACKEND=onnx|pytorch|remote` escolhe o adaptador do reranker. `remote` nao carrega modelo local.

## TwoStageRetriever
- Recebe um `RagContextPort` do estagio 1, um `Reranker` opcional, `top_n`, timeout e metricas.
- Executa o estagio 1, registra latencia, candidatos e scores antes do rerank.
- Se o reranker estiver desligado, devolve o resultado do estagio 1 sem alterar ordem ou scores.
- Se o reranker estiver habilitado, monta os documentos na ordem do estagio 1 e chama `rerank(query, documents, top_n)`.
- O resultado reranqueado usa `score` como score final e preserva `dense_score`, `sparse_score`, `rank` e `fused_score` do estagio 1.
- Timeout (`RERANK_TIMEOUT_SECONDS`), erro, resposta vazia, indice invalido ou reranker indisponivel fazem fallback para os primeiros top-N na ordem do estagio 1, marcando `rerank_fallback` e `rerank_applied=false`.
- O resultado expoe `rerank_applied`, `rerank_fallback`, `rerank_model` e `retrieval_mode` com sufixo `_reranked` ou `_fallback`.

## RemoteReranker
- Implementa o mesmo contrato `Reranker` do adaptador local.
- Configuracao por env:
  - `RERANKER_REMOTE_URL`
  - `RERANKER_REMOTE_API_KEY`
  - `RERANKER_REMOTE_MODEL`
  - `RERANK_TIMEOUT_SECONDS`
- Contrato HTTP:
  - `POST` no URL configurado, `Content-Type: application/json`, `Authorization: Bearer` quando houver chave.
  - Corpo: `{"model": "...", "query": "...", "documents": ["..."], "top_n": 4, "max_length": 512}`.
  - Resposta: `{"results": [{"index": 0, "score": 0.97}]}` com scores entre 0 e 1.
- Usa `SafeHttpClient`/`SSRFGuard`; em producao exige HTTPS. Indices duplicados ou fora do intervalo, score invalido, HTTP nao 2xx, resposta invalida ou timeout viram erro de reranker e disparam fallback no `TwoStageRetriever`.
- `status` usa `loaded=true` quando a URL esta configurada; nao faz chamada de rede no startup. O `/health` mostra backend `remote`.
- O modelo remoto recebe `max_length` e faz o truncamento; o adaptador local ja trunca no tokenizer e processa em lotes de `BATCH_SIZE`.

## Integracao
- LangGraph recebe `RagContextPort` e usa apenas `passages`, sem conhecer o backend.
- CrewAI recebe os trechos ja selecionados em `InterpretationRequest.rag_snippets`; nao acessa modelos.
- A composicao do worker escolhe:
  - antigo `KnowledgeRetriever` quando `HYBRID_RETRIEVAL_ENABLED=false`;
  - `TwoStageRetriever` sobre `HybridRetriever` quando a flag hibrida esta ligada.
- O `RetrievalRuntime` carrega o reranker local uma vez quando `RERANK_ENABLED=true` e backend local; com backend remoto apenas valida configuracao.

## Metricas e tracing
- Prometheus, com prefixo `paysentineliq_`:
  - `retrieval_stage_duration_seconds{stage}` para `embed`, `dense`, `sparse`, `fusion`, `stage1`, `rerank`, `total`.
  - `retrieval_candidates{stage}` para candidatos densos, esparsos, fundidos, do estagio 1 e reranqueados.
  - `retrieval_scores{stage}` para scores antes (`stage1`) e depois (`reranked`).
  - `retrieval_rerank_total{outcome}` para `success`, `disabled`, `timeout`, `error`, `empty` e `unavailable`.
- No worker, as metricas usam `PROMETHEUS_MULTIPROC_DIR` e aparecem no scrape do `/metrics` da API, que ja agrega os diretorios de api, worker e beat.
- OpenTelemetry: spans `retrieval.two_stage`, `retrieval.stage1` e `retrieval.rerank`, com atributos numericos e de resultado, sem texto de consulta ou documento.

## Configuracao adicional
- `RERANK_TIMEOUT_SECONDS` (padrao 5): timeout do estagio 2.
- `RERANKER_REMOTE_URL`, `RERANKER_REMOTE_API_KEY`, `RERANKER_REMOTE_MODEL`.
- `RERANKER_BACKEND` passa a aceitar `remote`.

## Criterios de aceite (viram testes)
1. Pipeline completo: estagio 1 top-K e reranker devolve top-N com scores e citacoes.
2. `RERANK_ENABLED=false`: estagio 1 intacto, sem chamada ao reranker.
3. Timeout: fallback para a ordem do estagio 1, com `rerank_fallback=timeout`.
4. Erro, resposta vazia e reranker indisponivel tambem fazem fallback.
5. `RemoteReranker` valida payload, resposta, erro HTTP e timeout.
6. Metricas registram latencia por estagio, candidatos, scores antes/depois e resultado do rerank.
7. Composicao mantem o caminho antigo quando a flag hibrida esta desligada.
8. Ruff, formatacao, mypy strict, import-linter e suite sem Docker verdes.

## Fora do escopo
- Alterar score antifraude, regras deterministicas, prompts ou modelo do Qwen.
- Calibrar pesos/RRF ou comparar qualidade de rerank com dados reais.
- Criar o servico remoto de reranking ou provisionar credenciais.
- Baixar modelos, executar reindexacao real ou medir latencia real em CPU.

## Validado nesta etapa
- Pipeline hibrido + reranker com fixtures: top-N, scores, citacoes, modo e contadores.
- Pipeline completo contra PGVector Docker: estagio 1 real, fusao e reranker fake retornando top-N.
- `RERANK_ENABLED=false`, timeout, erro, resposta vazia, indice invalido e reranker indisponivel com fallback.
- `RemoteReranker` com cliente HTTP fake: contrato, auth, ordenacao, HTTP nao 2xx, payload invalido, score invalido e timeout.
- Metricas Prometheus renderizadas com `stage`, candidatos, scores e outcomes; spans OTel verificados com exporter em memoria.
- Composicao do worker devolve `TwoStageRetriever` no caminho hibrido e mantem o retriever antigo com a flag desligada.

## Riscos e NAO VALIDADO
- Modelos reais, latencia e memoria do reranker local em CPU continuam NAO VALIDADOS.
- A API remota real, autenticacao, disponibilidade e formato exato do provedor ficam NAO VALIDADOS; o contrato acima e o esperado pelo adaptador.
- O timeout local cancela a espera, mas a thread de inferencia pode continuar ate terminar; isso e aceitavel para fallback, mas deve ser monitorado.
- A qualidade do top-N e a calibracao de scores dependem do reranker e de consultas reais.
