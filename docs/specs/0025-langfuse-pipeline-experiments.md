# SPEC 0025: Trace de analise e experimentos Langfuse (F2)

## Objetivo
Emitir um trace por analise, com spans de OCR, classificacao, retrieval, rerank, Qwen, guardrails e judge, e criar experimentos comparaveis no Langfuse a partir do dataset publico de eval. Tudo via porta `ObservabilityTracer`, sem acoplar agentes ao SDK.

## Trace por analise
- Trace raiz `analysis`, com `session_id` igual ao id da analise.
- Ambiente em `environment` e tag `env:<APP_ENV>`.
- Metadados: `analysis_id`, `document_id`, `document_type`, `otel_trace_id` e ambiente.
- Spans:
  - `ocr`: paginas, blocos, caracteres e sinais visuais, sem texto.
  - `classifier.document`: tipo de documento.
  - `classifier.risk`: score, banda, modelo e fallback de ML.
  - `retrieval`: modo, passageiros, flags e ordem antes/depois.
  - `retrieval.stage1`: candidatos e scores denso/esparso/fusao.
  - `retrieval.rerank`: ordem antes e depois, latencia, modelo e resultado.
  - `llm.interpret` ou `llm.crew_interpret`: modelo, prompt, tokens e latencia.
  - `guardrail.input`, `guardrail.output` e `guardrail.judge`.
  - `llm.judge`: modelo, prompt, tokens e latencia.
- Nenhum span envia OCR, imagem, bytes, prompt completo ou justificativa em claro.

## Scores
- `risk_score` numerico e `risk_band` categorico.
- `rerank_alterou_top1` booleano.
- `rerank_applied` booleano.
- `guardrail_failed` booleano.
- `judge_approved`, `judge_verdict` e `judge_findings`.

## Correlacao com OpenTelemetry
O trace do Langfuse recebe `otel_trace_id` nos metadados e o span OTel recebe `langfuse.trace_id`. O log `analysis_trace` inclui `analysis_id`, `otel_trace_id` e `langfuse_trace_id`.

## Dataset e experimentos
- Script `scripts/langfuse_experiment.py`.
- Le `.env.example` para a infraestrutura local e, opcionalmente, apenas as chaves `LANGFUSE_*` de um arquivo local.
- Envia `eval/retrieval_eval.jsonl` para o dataset `retrieval-eval-v1`, com perguntas publicas e sem PII.
- Roda quatro experimentos: denso, denso + rerank, hibrido RRF e hibrido RRF + rerank.
- Cada item usa engine e sessao proprios no loop da tarefa para evitar conflito asyncpg entre loops.
- Salva URLs e agregados em `eval/langfuse_experiment.json`.

## Testes
- Cliente falso cobrindo trace, spans, scores e IDs de correlacao.
- Teste de que os payloads nao contem CPF, valor, linha digitavel, e-mail, telefone ou nome.
- Teste de que o pipeline com `LANGFUSE_ENABLED=false` produz o mesmo resultado.
- Teste de que falha do cliente nao altera a analise.

## Criterios de aceite
1. Uma analise gera um trace com os spans e scores acima.
2. O experimento v3 aparece no Langfuse com 30 itens e quatro modos comparaveis.
3. Nenhum payload contem PII.
4. `make check` verde.

## Fora do escopo
- Usar prompt management do Langfuse. A versao do prompt vai nos metadados.
- Enviar imagens ou texto OCR.
- Rodar o experimento no CI sem chaves e rede.
