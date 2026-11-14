# SPEC 0012: Pipeline de agentes de IA (LangGraph, LangChain, CrewAI)

## Objetivo
Orquestrar o fluxo de analise de um documento (upload -> ingestao P06 -> classificacao -> agente de boleto/contracheque P07/P08 -> motor de fraude P09 -> interpretacao com RAG P10 -> persistencia/relatorio) com o mesmo codigo em local (LM Studio/Qwen) e producao (API OpenAI-compatible). O LLM explica e sugere; nunca decide o score sozinho.

## Papeis dos frameworks
- **LangGraph**: orquestra o grafo, estado tipado, nos, arestas condicionais por tipo e timeout por no. Nao usa checkpointer externo; o estado de cada etapa vai para `analyses` e o log para `analysis_events`.
- **LangChain Core**: somente prompts (`ChatPromptTemplate`) e parser de saida estruturada (`PydanticOutputParser`). Nao e o orquestrador.
- **CrewAI**: uma crew pequena com dois agentes (analista de evidencias + redator) que recebe evidencias deterministicas e trechos do RAG e devolve justificativa em linguagem clara e inconsistencias semanticas sugeridas.
- **LLMPort**: porta unica para o modelo; adaptador OpenAI-compatible configurado por `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`. O mesmo adaptador serve local/producao; so o ambiente muda.
- **Guardrails completos** ficam para a P12. A P11 aplica apenas limites de autonomia e redacao.

## Fluxo do grafo
1. `load`: carrega metadados do documento e bytes do bucket do dono.
2. `ingest`: P06 (OCR/visao) devolve texto e sinais visuais.
3. `classify`: boleto (BANK_SLIP) ou contracheque (PAYSLIP); recibos ficam para a P14.
4. `boleto`/`payslip`: regras P07/P08.
5. `fraud`: P09 (regras + ML + visao).
6. `rag`: P10 consulta a base com filtros; se falhar, `rag_unavailable`.
7. `interpret`: CrewAI com evidencias e trechos; se falhar, `llm_unavailable`.
8. `persist`: grava estado/score/versoes em `analyses`, eventos em `analysis_events` e o relatorio JSON no bucket.

Cada no registra um evento (`processing`, `rule_triggered`, `degraded`, `completed`/`failed`) e faz timeout configuravel. Falha de LLM/RAG/ML nao derruba a analise: ela termina com o que houver e a flag correspondente.

## LLM e saida estruturada
- Temperatura baixa (0.1), prompts curtos e esquema simples (`justification` + no maximo 5 `inconsistencies`).
- Pedir JSON, validar com Pydantic, tentar reparo uma vez e repetir com limite. JSON invalido/timeout viram `llm_unavailable`.
- Prompts versionados em `infrastructure/ai/prompts/{pt,es,en}.md`; a versao e o hash do arquivo.
- Nenhum prompt/evento contem nome, CPF/CNPJ, salario, endereco, e-mail, telefone ou texto do documento. A redacao envia apenas codigos de regra, severidade, score, trechos publicos do RAG e flags. A partir da P12, o prompt recebe tambem um excerto sanitizado, mascarado e truncado do documento, delimitado como dado nao confiavel (SPEC 0013/ADR-0016).
- Telemetria/tracing de CrewAI, LangChain/LangSmith e Chroma desligados por ambiente; a CrewAI e criada com `tracing=False`.

## Score e autonomia
- O score base vem de P09 (deterministico + ML + visual), com piso critico 80.
- Sugestoes do LLM podem somar no maximo `LLM_MAX_SCORE_ADJUSTMENT` (default 5) pontos; nunca reduzem o score, nunca removem evidencia e nunca ignoram o piso critico.
- `AnalysisReport` registra `base_score`, `llm_adjustment`, `score` final e as flags; a justificativa e as sugestoes sao explicitamente do LLM.

## Persistencia
- `analyses`: id, owner_id, document_id, tipo, status, score, classe, versao das regras, versoes dos modelos, flags, estado JSON sem PII, chave S3 do relatorio e erro.
- `analysis_events` append-only (somente INSERT): analysis_id, tipo do evento, codigo da regra, versao das regras, versao do modelo, flags, payload JSON somente com ids/codigos/numeros e timestamp.
- Relatorio JSON em `users/{owner_id}/analyses/{analysis_id}/report.json` (bucket do dono, P05).
- O score final deve ser reproduzivel a partir dos eventos e das versoes registradas.

## Caso de uso
- `RunAnalysisUseCase(document_id)` on-demand (sem fila), testavel, recebe o dono do documento e retorna `AnalysisReport`.
- Depende de portas: documento, orquestrador, repositorios de analise/eventos, relogio. Frameworks de IA somente na infraestrutura.

## Criterios de aceite (viram testes)
1. LLMPort/adaptador OpenAI-compatible: sucesso, retry, timeout, erro HTTP, resposta invalida; SSRF guard aplicado.
2. Prompts pt/es/en carregados e versionados; parser Pydantic valida JSON, tenta reparo e respeita o limite.
3. CrewAI fake devolve justificativa/sugestoes; sugestoes nao reduzem score, tem teto e nao removem evidencia.
4. LangGraph percorre documento sintetico (boleto e contracheque) com LLM falso; cada no grava evento/estado.
5. Falha de LLM, RAG ou ML gera a flag e a analise termina.
6. `analysis_events` so recebe INSERT e nao contem PII/texto; score reproduzivel pelos eventos/versoes.
7. Relatorio JSON e gravado no bucket do dono com score/classe/campos/evidencias/justificativa/versoes/flags.
8. Telemetria desligada; import-linter impede frameworks de IA no dominio/aplicacao.
9. Teste manual do LM Studio real e NÃO VALIDADO sem o modelo local.

## Fora do escopo
- Endpoint HTTP (P13), fila, guardrails completos (P12), recibos (P14), autonomia com ferramentas, agentes que decidem score, memoria persistente de agente, checkpointer LangGraph, tracing externo.

## Riscos
- Modelo 4B pode produzir JSON invalido ou justificativa fraca; reparo limitado e fallback deterministico.
- CrewAI real nao foi executado sem LM Studio; o caminho real fica NÃO VALIDADO.
- O ajuste do LLM e conservador e limitado; o score base continua auditavel.
- Dados sinteticos nao medem qualidade real de explicacao.
