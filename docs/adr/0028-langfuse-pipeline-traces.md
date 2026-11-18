# ADR 0028: Trace ponta a ponta por analise e experimentos Langfuse

- Status: aceito
- Data: 2026-11-18
- Relacionado: SPEC 0025, ADR 0027

## Contexto
A F1 criou a porta `ObservabilityTracer` e os adapters Langfuse/Noop, mas os spans cobriam apenas as chamadas de interpretacao e judge. A F2 precisa de um trace por analise com OCR, classificacao, retrieval, rerank, Qwen, guardrails e judge, alem de experimentos comparaveis sobre o dataset publico de retrieval.

## Decisao
- Abrir um trace `analysis` no inicio do grafo, com `session_id` igual ao id da analise e ambiente em atributo e tag.
- Instrumentar os nos do grafo e o `TwoStageRetriever` pela porta, sem importar Langfuse no dominio ou na aplicacao.
- Registrar tokens, latencia e versao do prompt nas geracoes.
- Expor `score` na porta para registrar risco, rerank, guardrails e judge no trace.
- Propagar `otel_trace_id` no trace e `langfuse.trace_id` no span OTel, e logar ambos.
- Publicar o dataset de eval como dataset Langfuse e rodar quatro modos via `dataset.run_experiment`.
- Usar engine e sessao proprios por item de experimento, dentro do loop da tarefa.

## Justificativa
- A porta mantem os agentes e o grafo independentes do SDK e permite Noop ou cliente falso nos testes.
- O trace na raiz e os spans filhos dao visao ponta a ponta sem enviar texto sensivel.
- Scores nativos do Langfuse tornam a comparacao entre modos direta.
- Engine por item evita o erro de asyncpg quando o loop do experimento difere do loop que criou o pool.

## Consequencias
- Tokens do CrewAI podem ficar ausentes; o metadado `tokens_available` indica isso.
- O trace usa hashes e agregados em vez de prompts e justificativas completas.
- O dataset de experimento precisa continuar publico; o script bloqueia perguntas com possiveis identificadores.
- O experimento completo depende de rede, chaves e modelos locais e nao entra no CI.
