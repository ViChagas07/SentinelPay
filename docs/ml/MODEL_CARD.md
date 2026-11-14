# MODEL CARD — classificador de risco antifraude (sintetico)

## Finalidade
Complementar as regras deterministicas de boleto e contracheque com:
- uma probabilidade calibrada de adulteracao;
- um score de anomalia para valores e combinacoes fora do padrao;
- sinais visuais heuristicos da P06.

O modelo nao decide sozinho, nao substitui revisao humana e nao deve ser usado como prova de fraude.

## Dados
- Origem: **100% sintetica**, gerada por `paysentineliq.ml.synthetic`; nenhum documento real ou dado pessoal.
- Semente fixa e mutacoes rotuladas (`valid`, `value_changed`, `dv_invalid`, `sum_mismatch`, `duplicated_item`, `invalid_tax_id`, `pasted_region`, `missing_table`, `unknown_layout`, `low_confidence`).
- Split por `base_id` para impedir vazamento entre treino/validacao/teste.
- `missing_table`, `unknown_layout` e `low_confidence` sao label 0 (nao adulterado) para evitar que ausencia/ilegibilidade vire fraude.

## Features
- Subscore deterministico, contagens/severidades de evidencias, indicador por regra, confiancas de campo, `not_validated`, contagens/razoes de itens e valores.
- Sinais visuais agregados (quantidade, maximo e media).
- Sem texto bruto, nome, CPF/CNPJ, endereco ou payload do documento.

## Modelos
- Anomalia: `IsolationForest` (100 arvores) treinado apenas nas linhas validas do treino.
- Classificacao: `CalibratedClassifierCV` sigmoid (cv=3) sobre `Pipeline([StandardScaler, LogisticRegression(class_weight="balanced")])`.
- Versao inicial: `fraud-risk-v1`.

## Metricas (SINTETICAS)
As metricas abaixo sao geradas por `make train` e marcadas `synthetic=True` no registro. Elas NAO representam desempenho em dados reais.

| Metrica | Valor |
| --- | --- |
| Dataset | sintetico |
| Seed | a preencher pelo treino |
| Bases | a preencher pelo treino |
| Linhas | a preencher pelo treino |
| Precision | a preencher |
| Recall | a preencher |
| F1 | a preencher |
| ROC-AUC | a preencher |
| PR-AUC | a preencher |
| Brier | a preencher |
| Curva de calibracao | a preencher |

## Limites e riscos
- Dados sinteticos podem ser separaveis demais; metricas altas sao esperadas e nao provam desempenho real.
- Nao ha avaliacao de drift, fraude adversarial, vies ou justica; nada disso esta validado.
- Sinais visuais sao heuristica e podem gerar falso positivo.
- O modelo pode errar; o piso critico deterministico e a revisao humana continuam obrigatorios.
- O artefato e local (`models/artifacts/`, fora do git) e o carregamento exige caminho confiavel + SHA-256; isso reduz risco de troca, mas nao valida a qualidade do modelo.
- O modelo nao deve ser promovido a producao com dados reais sem novo treino, calibracao, avaliacao e aprovacao.

## Registro e reprodutibilidade
- `make train` gera o artefato `.joblib` e o registro `.json` com versao, SHA-256, hash/descricao do dataset, feature names e metricas sinteticas.
- O dataset e o treino usam semente fixa; mudancas de features exigem nova versao do modelo.
- `FraudScoringService` funciona sem o modelo, caindo no deterministico e sinalizando `ml_unavailable`.
