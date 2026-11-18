# Observabilidade de LLM com Langfuse

## Visao geral
O `ObservabilityTracer` instrumenta a analise inteira atras da flag `LANGFUSE_ENABLED`. O padrao e `NoopTracer`; sem flag, sem chaves ou com falha de inicializacao, nenhum dado sai da aplicacao. Quando ligado, cada analise gera um trace com spans de OCR, classificacao, retrieval, rerank, Qwen, guardrails e judge.

## Configuracao
Variaveis lidas pelo backend e repassadas pelo Compose:

| Variavel | Padrao | Uso |
| --- | --- | --- |
| `LANGFUSE_ENABLED` | `false` | Liga o `LangfuseTracer`. |
| `LANGFUSE_PUBLIC_KEY` | vazio | Chave publica do projeto Langfuse. |
| `LANGFUSE_SECRET_KEY` | vazio | Chave secreta do projeto Langfuse. Nunca versionar. |
| `LANGFUSE_HOST` | vazio | Host do Langfuse; vazio usa `LANGFUSE_BASE_URL` ou `https://cloud.langfuse.com`. |
| `LANGFUSE_BASE_URL` | vazio | Alias aceito para o host, compativel com o SDK. |
| `LANGFUSE_SAMPLE_RATE` | `1.0` | Amostragem de traces entre 0 e 1. |

O `.env.example` contem apenas placeholders vazios. Chaves reais ficam no `.env` local, que e ignorado pelo git, ou no ambiente do processo. O Compose do projeto usa `.env.example` por padrao; para um teste local com Langfuse, exporte as variaveis no shell ou use um arquivo de ambiente local explicito, sem commitar o arquivo.

## Trace por analise
- Trace raiz `analysis`, com `session_id` igual ao id da analise.
- Ambiente em `environment` e tag `env:<APP_ENV>`.
- Metadados: `analysis_id`, `document_id`, `document_type`, `otel_trace_id` e ambiente.
- Spans emitidos:
  - `ocr`: paginas, blocos, caracteres e sinais visuais.
  - `classifier.document`: tipo de documento.
  - `classifier.risk`: score, banda, modelo e fallback de ML.
  - `retrieval`: modo, passagens e flags.
  - `retrieval.stage1`: candidatos e scores denso/esparso/fusao.
  - `retrieval.rerank`: ordem antes e depois, latencia, modelo e resultado.
  - `llm.interpret` ou `llm.crew_interpret`: modelo, versao do prompt, tokens e latencia.
  - `guardrail.input`, `guardrail.output` e `guardrail.judge`.
  - `llm.judge`: modelo, versao do prompt, tokens e latencia.
- A versao de cada prompt vai nos metadados da geracao. Prompt management do Langfuse nao e usado.
- `rerank_alterou_top1` e calculado comparando o primeiro documento antes e depois do rerank.

## Scores no trace
- `risk_score` numerico e `risk_band` categorico.
- `rerank_alterou_top1` e `rerank_applied` booleanos.
- `guardrail_failed` booleano.
- `judge_approved`, `judge_verdict` e `judge_findings`.

## O que e enviado
- Metadados estruturados: modelo, versao do prompt, temperatura, limite de tokens, tipo de documento, score, banda, idioma, flags de degradacao e resultado.
- Evidencias: regra, severidade, peso e chave de mensagem.
- Entrada e saida de texto: apenas SHA-256 e tamanho.
- Identificadores de usuario: HMAC-SHA256 com `SECURITY_HASH_SECRET`.
- IDs de analise, documento, requisicao e regra: mantidos como identificadores opacos.

## O que e mascarado ou nunca enviado
- CPF e CNPJ com e sem formatacao.
- Nomes de pessoas em campos estruturados e linhas rotuladas em portugues, espanhol e ingles.
- Valores monetarios, inclusive `R$` e campos como `amount`, `salary` e `total`.
- Linha digitavel de 47/48 digitos e codigo de barras de 44 digitos.
- E-mail, telefone, chave PIX, CEP e enderecos.
- JWT, Bearer, chaves de API, senhas e segredos.
- Texto OCR bruto, excertos completos de documento, imagens e bytes.

Campos de texto livre sao substituidos por `{"sha256": "...", "length": N}`. Campos de usuario sao substituidos por `sha256:<hmac>`. Nomes nao rotulados em texto livre nao sao enviados porque o texto livre do documento nao sai da aplicacao.

## Defesa em profundidade
O mascaramento central roda antes de chamar o SDK. O callback `mask` do Langfuse recebe o mesmo mascarador como segunda barreira, cobrindo qualquer dado que o SDK tente serializar por outro caminho.

## Falhas e latencia
- O cliente usa timeout de 2 segundos, lote de 10 spans e intervalo de flush de 2 segundos.
- O envio e assincrono no SDK e nao bloqueia a analise.
- `flush` e `shutdown` rodam em thread com timeout de 2 segundos no encerramento do lifespan ou do runtime do worker.
- Qualquer erro de inicializacao, atualizacao, score, flush ou shutdown e registrado sem payload e nao propaga.
- O `NoopTracer` devolve handles vazios e nao altera resposta, score, evidencias ou justificativa.

## Correlacao com OpenTelemetry
O trace do Langfuse recebe `otel_trace_id` nos metadados e o span OTel recebe `langfuse.trace_id`. O log `analysis_trace` inclui `analysis_id`, `otel_trace_id` e `langfuse_trace_id`, permitindo ligar os dois sistemas.

## Dataset e experimentos
O script `scripts/langfuse_experiment.py` publica `eval/retrieval_eval.jsonl` no dataset `retrieval-eval-v1` e roda quatro experimentos comparaveis no Langfuse: denso, denso + rerank, hibrido RRF e hibrido RRF + rerank. O dataset contem apenas perguntas publicas, sem PII.

Execucao de referencia em 2026-11-18, prefixo `sentinelpay-retrieval-v3`, 30 itens por experimento e 0 falhas:

| Modo | Recall@5 | MRR | Top1 | p50 |
| --- | --- | --- | --- | --- |
| Denso (BGE-M3) | 0.9333 | 0.8917 | 0.8333 | 134.65 ms |
| Denso + rerank | 0.9667 | 0.9611 | 0.9333 | 14586.85 ms |
| Hibrido RRF | 0.8667 | 0.8011 | 0.7333 | 135.95 ms |
| Hibrido RRF + rerank | 0.9667 | 0.9417 | 0.9000 | 14411.64 ms |

Experimentos:
- Denso: https://us.cloud.langfuse.com/project/cmwm4p0y80145ad0d02cx7xjk/experiments/results?baseline=90fea7f263d5f3fa
- Denso + rerank: https://us.cloud.langfuse.com/project/cmwm4p0y80145ad0d02cx7xjk/experiments/results?baseline=12815ab6c8963ec3
- Hibrido RRF: https://us.cloud.langfuse.com/project/cmwm4p0y80145ad0d02cx7xjk/experiments/results?baseline=41cde83c4b156ed7
- Hibrido RRF + rerank: https://us.cloud.langfuse.com/project/cmwm4p0y80145ad0d02cx7xjk/experiments/results?baseline=575234a66b899daf

O resultado local fica em `eval/langfuse_experiment.json`.

## Como validar
- `poetry -C backend run pytest tests/unit/test_observability_masking.py tests/unit/test_langfuse_tracer.py tests/unit/test_langgraph_orchestrator.py -q`
- `make check`
- `poetry -C backend run python ../scripts/langfuse_experiment.py --langfuse-env-file ../.env --experiment-prefix sentinelpay-retrieval-v4`
- Com chaves em um ambiente local isolado, ligue `LANGFUSE_ENABLED=true` e rode uma analise que use LLM. Verifique no Langfuse um trace `analysis` com os spans e scores acima.

## Nao validado
- O trace de uma analise real com LLM no Langfuse Cloud ainda depende de um ambiente com LM Studio, worker, S3 e banco local ativos. A suite valida o payload com cliente falso.
- A qualidade e a retencao dos traces no projeto Langfuse sao responsabilidade da conta usada.
- Nomes sem rotulo em texto livre nao sao detectados por heuristica; por isso esse tipo de texto nao e enviado.
- O prompt management do Langfuse nao foi usado; a versao do prompt vai nos metadados.
