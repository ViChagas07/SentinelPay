# ADR 0015: Agentes de IA com LangGraph, LangChain e CrewAI

- Status: aceito
- Data: 2026-11-14

## Contexto
A P11 precisa unir ingestao, agentes de boleto/contracheque, motor de fraude, RAG e explicacao em um fluxo unico, local (LM Studio/Qwen) e producao (OpenAI-compatible), sem entregar ao LLM o poder de decidir o score. Nao ha endpoint/queue nesta fase, e a P12 fara os guardrails completos.

## Decisao
- **LangGraph** orquestra o fluxo com estado tipado, nos e arestas condicionais. Cada no tem timeout e grava estado/evento. Nao usamos checkpointer externo: persistimos em `analyses` e `analysis_events` (YAGNI).
- **LangChain Core** entra apenas como `ChatPromptTemplate` e `PydanticOutputParser`.
- **CrewAI** executa uma crew pequena (analista de evidencias + redator) e devolve justificativa e inconsistencias semanticas. `tracing=False` e telemetria desligada por ambiente.
- **LLMPort** + adaptador OpenAI-compatible e a camada de modelo; `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` mudam por ambiente. O adaptador direto usa a guarda SSRF da P03; a URL do CrewAI e validada pela mesma guarda antes do uso.
- Saidas sao Pydantic, JSON, temperatura 0.1, prompts curtos versionados por hash em `infrastructure/ai/prompts/{pt,es,en}.md`; reparo uma vez e limite de tentativas.
- O score base vem de P09. O LLM so pode **somar** ate `LLM_MAX_SCORE_ADJUSTMENT` (default 5) por sugestoes; nunca reduz, nunca remove evidencia e nunca fura o piso critico 80.
- Falha de LLM/RAG/ML marca `llm_unavailable`/`rag_unavailable`/`ml_unavailable` e a analise continua com o que houver.
- Prompts e eventos nao levam PII nem texto do documento; eventos guardam somente ids/codigos/severidade/pesos/score/versoes/flags.
- O relatorio JSON completo fica no bucket do dono; a tabela `analyses` guarda estado sem PII e a chave do relatorio.
- `analysis_events` e append-only (somente INSERT) e serve para reconstruir o score e auditar.
- Frameworks de IA ficam somente em `application/ports` (interfaces) e `infrastructure`; o import-linter proibe no dominio/aplicacao.

## Alternativas descartadas
- **LLM decide o score:** viola a fonte unica deterministica e a auditabilidade.
- **CrewAI como orquestrador:** menos controle de estado/condicionais/timeout que LangGraph.
- **LangGraph checkpointer:** duplicaria persistencia sem necessidade; a tabela de analises ja e a fonte.
- **Agentes com ferramentas/autonomia ampla:** fica para a P12; risco de prompt injection e acoes nao auditadas.
- **Enviar texto/PII ao LLM:** viola LGPD e as regras de privacidade.
- **Segundo cliente LLM para local/producao:** aumentar�a divergencia; usamos um adaptador configuravel.
- **Tracing externo:** telemetria/tracing de terceiros desligados; nenhum dado sai para LangSmith/CrewAI.

## Consequencias
- O fluxo tem explicacao e sugestoes, mas o score continua deterministico e reproduzivel.
- O caminho CrewAI/LM Studio real nao foi executado sem modelo local; fica NÃO VALIDADO. Testes usam LLM/crew falsos.
- O reparo de JSON e o timeout limitam falhas de modelos pequenos.
- O ajuste do LLM e conservador (<=5) e o piso critico permanece.
- A P12 podera adicionar guardrails de entrada/saida e a P13 o endpoint; a P14, recibos.
