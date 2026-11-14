# SPEC 0010: ML antifraude (Scikit-learn) e fusao de score

## Objetivo
Complementar as regras deterministicas com (a) deteccao de anomalias nao supervisionada e (b) classificador supervisionado calibrado, usando somente features derivadas das saidas deterministicas e dos sinais visuais da P06. Sem dados reais, sem deep learning, sem LLM e sem promessa de acuracia.

## Dados e honestidade
- Dataset 100% sintetico, gerado por `paysentineliq.ml.synthetic` com semente fixa.
- Cada linha representa um documento-base (`base_id`) e uma mutacao rotulada (`valid`, `value_changed`, `dv_invalid`, `sum_mismatch`, `duplicated_item`, `invalid_tax_id`, `pasted_region`, `missing_table`, `unknown_layout`, `low_confidence`).
- O split treino/validacao/teste e por `base_id`; todas as variantes de um documento-base ficam no mesmo split.
- `missing_table`, `unknown_layout` e `low_confidence` sao rotulados como nao adulterados (label 0), para ensinar o modelo a nao tratar ausencia/ilegibilidade como fraude.
- Nenhuma metrica pode ser apresentada como desempenho real: toda metrica e marcada `synthetic=True` no registro e no model card.

## Features
- Derivadas de `BoletoAnalysis`/`PayslipAnalysis`: subscore, contagem e severidade das evidencias, indicador por regra, confiancas de campo, `not_validated`, contagens de itens, razoes de valores (descontos/proventos, liquido/proventos), `amount_log`, fator de vencimento normalizado e status do codigo de barras.
- Sinais visuais da P06 agregados: quantidade, maximo e media dos valores de `VisualSignal` (0..1).
- Sem texto bruto, sem nome, sem CPF/CNPJ, sem endereco, sem payload do documento.
- `FEATURE_NAMES` e versionado; o artefato registra os nomes e o carregador recusa incompatibilidade.

## Modelos
- Anomalia: `IsolationForest` treinado somente nas linhas validas do treino; score normalizado pela distribuicao de treino valida.
- Classificacao: `CalibratedClassifierCV` (sigmoid, cv=3) sobre `Pipeline([StandardScaler, LogisticRegression(class_weight="balanced")])`; pre-processamento dentro do pipeline.
- Probabilidade calibrada e score de anomalia sao expostos separadamente no resultado.

## Fusao
- `FraudScoringService` combina:
  - subscore deterministico (0..100);
  - componente ML = `probability * (1 - anomaly_weight) + anomaly_score * anomaly_weight` (0..1 -> 0..100);
  - componente visual = maximo dos sinais visuais (0..1 -> 0..100).
- Pesos iniciais: deterministico 0.60, ML 0.30, visual 0.10; `anomaly_weight=0.20`; cortes Baixo <=39, Atencao <=69, Alto >=70. Todos marcados "a calibrar com dados reais".
- Se o modelo nao estiver carregado ou falhar, os pesos deterministico/visual sao renomeados para somar 1 e o resultado marca `ml_unavailable=True`.
- Regra critica disparada impoe piso 80 ao score final.
- Score final 0..100 inteiro, deterministicamente arredondado; bands `low`, `attention`, `high`.

## Registro de modelos
- Artefatos em `models/artifacts/` (fora do git): `.joblib` + registro `.json` com versao, SHA-256 do artefato, hash/descricao do dataset, feature names, metricas sinteticas e flag `synthetic`.
- Carregamento apenas de diretorio confiavel, com path resolvido dentro da raiz e SHA-256 conferido antes de `joblib.load`.
- Hash invalido, path traversal ou feature names divergentes sao recusados com erro.

## Criterios de aceite (viram testes)
1. Features sao numericas, na ordem de `FEATURE_NAMES`, sem texto bruto; factories cobrem boleto e contracheque.
2. Dataset sintetico e deterministico para a mesma semente; split nao vaza `base_id`; rotulos de mutacao sao explicitos.
3. Treino produz pipeline calibrado, IsolationForest, metricas sinteticas e artefato com hash.
4. Carregador recusa hash invalido, path fora da raiz e feature names diferentes.
5. Servico funciona com modelo fake e sem modelo; sem modelo marca `ml_unavailable` e usa deterministico/visual.
6. Regra critica impoe piso 80; mais evidencia critica nao reduz o score.
7. Metrica e saida ML sao marcadas como sinteticas.
8. `make train` roda em dataset pequeno e `make check` fica verde.

## Fora do escopo
- Dados reais, rotulos humanos, deep learning, LLM, endpoint, banco de features, MLflow, treino distribuido, fairness formal e promessa de acuracia.
- Usar texto bruto de documento ou PII como feature.
- Alterar as regras deterministicas da P07/P08.

## Riscos
- Dataset sintetico pode ser separavel demais; metricas altas nao significam desempenho real.
- Distribuicao real, fraude adversarial e drift nao foram medidos.
- Sinais visuais sao heuristica e podem gerar falso positivo.
- O modelo so deve complementar as regras; o piso critico e a revisao humana continuam necessarios.
- Artefatos sao locais e nao versionados; o hash protege contra troca, mas nao contra um artefato malicioso treinado.
