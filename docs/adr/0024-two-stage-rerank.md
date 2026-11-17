# ADR 0024: Reranking top-N e adaptador remoto

- Status: aceito
- Data: 2026-11-17

## Contexto
A ETAPA B entregou o estagio 1 hibrido com top-K 25 atras de `HYBRID_RETRIEVAL_ENABLED`. A ETAPA C precisa reduzir os candidatos para top-N 4 antes do Qwen, manter o caminho antigo quando o reranker esta desligado e permitir um reranker hospedado em producao sem mudar a interface dos agentes.

## Decisao
- Criar `TwoStageRetriever` na camada de aplicacao, compondo `RagContextPort` do estagio 1 e `Reranker` do estagio 2.
- Quando `RERANK_ENABLED=false`, o `TwoStageRetriever` devolve o top-K do estagio 1 na ordem original, sem chamar o reranker.
- Quando `HYBRID_RETRIEVAL_ENABLED=false`, a composicao mantem o `KnowledgeRetriever` antigo e nao cria o pipeline de dois estagios.
- Aplicar timeout do reranker no `TwoStageRetriever`; timeout, erro, resposta vazia ou reranker indisponivel fazem fallback para os primeiros top-N do estagio 1.
- Criar `RemoteReranker` com o mesmo contrato `Reranker`, usando `SafeHttpClient` e `SSRFGuard`, selecionado por `RERANKER_BACKEND=remote`.
- Manter o adaptador local `BgeRerankerV2M3`, com lotes e truncamento por `RERANK_MAX_LENGTH`.
- Adicionar metricas Prometheus por estagio, candidatos, scores antes/depois e resultado do rerank; adicionar spans OpenTelemetry sem texto de consulta.
- Manter `RagContextPort` como unica interface entregue ao LangGraph e ao CrewAI.

## Alternativas consideradas
- **Rerankar dentro do `HybridRetriever`:** misturaria as responsabilidades e impediria testar a flag desligada de forma isolada.
- **Colocar o timeout no adaptador local:** `asyncio.to_thread` nao cancela a thread de inferencia; o timeout de espera fica no orquestrador, que decide o fallback.
- **Usar `httpx.AsyncClient` direto no reranker remoto:** evita a protecao de SSRF e a validacao de URL; o projeto ja tem `SafeHttpClient`.
- **Incluir os modelos no LangGraph/CrewAI:** acoplaria os agentes a ONNX, PyTorch ou HTTP; a interface `RagContextPort` ja resolve.
- **Persistir scores e metricas em tabela:** aumentaria escrita por analise; Prometheus/OTel sao suficientes para esta fase.

## Consequencias
- O top-N passa a ser o contrato do Qwen quando o reranker esta habilitado; sem reranker, o top-K do estagio 1 permanece.
- O fallback e observavel por `rerank_fallback`, `rerank_applied` e pela metrica `retrieval_rerank_total{outcome}`.
- O backend remoto exige contrato HTTP e disponibilidade externa; o servico real e as credenciais ficam NAO VALIDADOS.
- O timeout local nao interrompe a thread de inferencia, apenas libera a analise com fallback.
- As metricas do worker aparecem no `/metrics` da API via multiprocess Prometheus.
