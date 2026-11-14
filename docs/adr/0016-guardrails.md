# ADR 0016: Guardrails em 4 camadas contra prompt injection

- Status: aceito
- Data: 2026-11-14

## Contexto
A P11 colocou OCR, RAG e LLM no fluxo de analise. Texto extraido de documento e trecho recuperado sao dados nao confiaveis e podem conter instrucoes (injecao indireta). O LLM tambem pode devolver justificativa incoerente, com PII, segredos ou URLs. A P12 precisa reduzir esse risco sem entregar ao modelo a decisao do score e sem quebrar a analise quando uma defesa opcional falhar.

## Decisao
- **Defesa em profundidade em 4 camadas**: (1) system prompt fixo com delimitadores e regra dado-nao-instrucao; (2) codigo obrigatorio (sanitizacao, padroes, allowlist de ferramentas, esquema estrito, varredura de PII/segredo, remocao de URL); (3) classificador leve `scikit-learn` opcional sobre o texto sanitizado; (4) LLM-as-a-judge opcional com `LLM_JUDGE_MODEL` e veredito estruturado.
- **Camadas 1 e 2 sempre ligadas**; 3 e 4 ligadas por configuracao. Falha de camada opcional gera flag e a analise continua.
- **Score intocavel**: a extracao deterministica usa o texto OCR original; a sanitizacao/classificacao so alimenta deteccao, evidencias e o prompt. Injecao detectada suprime o ajuste do LLM e a explicacao passa a ser template deterministico. Reprovacao do judge tambem zera o ajuste.
- **Deteccao e evidencia, nao descarte**: achados viram `AnalysisEvidence` (`guardrail.*`, peso 0, severidade) e evento `guardrail_triggered`; o payload nao leva texto nem PII.
- **Saida validada**: Pydantic `extra="forbid"` + limites, varredura de PII/segredos/termos do documento, remocao de URL fora da allowlist. Violacao bloqueia a saida e aciona template a partir das evidencias.
- **Portas na aplicacao** (`InjectionClassifierPort`, `ReportJudgePort`, `GuardrailMetricsPort`); `sklearn`, adaptadores de LLM e contadores ficam na infraestrutura. O dominio nao conhece frameworks.
- **Allowlist de ferramentas vazia**: os agentes nao recebem ferramentas; qualquer pedido futuro de ferramenta fora da allowlist e rejeitado.
- **Metricas sem PII**: contador `(layer, code)` para a P16; nada de texto, documento ou dado pessoal.
- **Modelo sintetico com cobertura limitada**: o classificador e treinado em exemplos sinteticos e o model card registra explicitamente que nao houve ataque real/adaptativo.

## Alternativas descartadas
- **Confiar so no prompt**: injecao indireta e adaptativa; prompt sozinho nao e defesa suficiente.
- **Descartar o documento quando houver suspeita**: perderia a analise; a deteccao vira evidencia e o score deterministico segue.
- **Deixar o LLM ajustar o score mesmo com injecao detectada**: violaria a fonte unica deterministica e a regra de que texto de documento nao e instrucao.
- **Classificador/LLM obrigatorios**: aumentaria custo/latencia e criaria dependencia de modelo; camadas 3/4 sao opcionais e degradam.
- **Filtro de palavras isolado**: gera falsos positivos e falsos negativos; usamos padroes + contexto + sinais de sanitizacao + classificador opcional + judge opcional.
- **Enviar o texto completo ao LLM/judge**: privacidade e custo; o prompt recebe excerto sanitizado, mascarado e truncado, e o judge recebe apenas o relatorio e as evidencias.

## Consequencias
- O score continua reproduzivel e imune a texto injetado; a explicacao pode ser mais conservadora (template) quando ha suspeita.
- Ha rastro auditavel por evidencia/evento/metrica, sem PII.
- Falsos positivos suprimem a explicacao do LLM, mas nunca o score; falsos negativos residuais sao possiveis.
- **NAO VALIDADO**: ataques reais/adaptativos, desempenho do classificador fora dos dados sinteticos e judge no modelo real. O sistema nao e declarado imune.
- A base `knowledge/` nao e varrida nesta fase; injecao via RAG depende de delimitadores e do judge.
- A allowlist de ferramentas e vazia hoje; a P13+ deve revisar antes de habilitar qualquer ferramenta.
