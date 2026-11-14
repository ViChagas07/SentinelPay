# ADR 0013: Fusao deterministica + ML + sinais visuais

- Status: aceito
- Data: 2026-11-14

## Contexto
As fases P07/P08 produzem evidencias deterministicas, subscores e itens de validacao. A P06 produz sinais visuais heurísticos. A P09 pede modelos classicos para complementar as regras, mas nao ha dados reais rotulados e o projeto nao pode prometer acuracia.

## Decisao
- Adotar dois modelos sklearn: `IsolationForest` nao supervisionado (treinado em documentos sinteticos validos) e `CalibratedClassifierCV(LogisticRegression)` supervisionado, com `StandardScaler` e classificador dentro do pipeline.
- Features sao numericas e derivadas somente de saidas deterministicas e sinais visuais; texto bruto e PII ficam fora.
- O `FraudScoringService` combina deterministico, ML e visual com pesos/cortes configuraveis. Valores iniciais sao explicitamente marcados "a calibrar com dados reais":
  - deterministico 0.60, ML 0.30, visual 0.10;
  - dentro do ML, probabilidade 0.80 e anomalia 0.20;
  - Baixo <=39, Atencao <=69, Alto >=70;
  - piso critico 80.
- Se o modelo nao estiver carregado ou falhar, os pesos deterministico/visual sao renomeados para somar 1 e a saida marca `ml_unavailable=True`.
- O score deterministico continua sendo a fonte principal; o ML complementa e nunca remove uma regra critica.
- Dataset sintetico com semente fixa, mutacoes rotuladas e split por `base_id`; metricas sao sempre marcadas como sinteticas.
- Artefatos em `models/artifacts/` fora do git, com SHA-256 e carregamento somente de caminho confiavel; `joblib.load` so ocorre depois da verificacao.
- O model card registra finalidade, dados, features, limites, metricas sinteticas e riscos.

## Alternativas descartadas
- **ML isolado decidindo o score:** descartado; reduziria auditabilidade e permitiria que um modelo sintetico anulasse uma regra critica.
- **Deep learning/LLM:** descartado por falta de dados, custo, opacidade e escopo.
- **Dados reais nesta fase:** descartado; nao ha base rotulada com governanca/LGPD.
- **Pesos fixos sem configuracao:** descartado; os pesos e cortes precisam ser recalibrados com dados reais.
- **Confiar no artefato sem hash:** descartado; pickle/joblib executa codigo e um arquivo trocado e risco de RCE.
- **Incluir texto bruto ou PII nas features:** descartado por LGPD e por risco de o modelo memorizar dados.

## Consequencias
- O resultado e auditavel em componentes e mantem o piso critico.
- As metricas do model card sao apenas sinteticas; nao havera afirmacao de desempenho real.
- O modelo pode ser desligado sem derrubar a analise.
- O artefato e local e nao versionado; a reprodutibilidade vem do script `make train` e da semente.
- A proxima calibracao com dados reais exigira governanca, rotulos, avaliacao de vies e nova versao do modelo.
- A P11 pode usar `analysis_events` para auditoria sem PII; nada de Event Sourcing.
