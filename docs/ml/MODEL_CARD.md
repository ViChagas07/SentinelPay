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
As metricas abaixo sao do ultimo treino sintetico reproduzivel e marcadas `synthetic=True` no registro. Elas NAO representam desempenho em dados reais. Valores 1.0 refletem a separabilidade artificial do dataset sintetico.

| Metrica | Valor (teste) |
| --- | --- |
| Dataset | sintetico |
| Seed | 42 |
| Bases | 60 (36 treino / 12 validacao / 12 teste) |
| Linhas | 240 (144 treino / 48 validacao / 48 teste) |
| Dataset hash | `ccd1a6b3bfa1ae419eede959d90cc83a0663a09c6bcb711cc7bed8d6613ac16a` |
| Precision | 1.0 |
| Recall | 1.0 |
| F1 | 1.0 |
| ROC-AUC | 1.0 |
| PR-AUC | 0.9999999999999999 |
| Brier | 0.0023968040449143155 |
| Curva de calibracao | `(0.0402, 0.0)` e `(0.9566, 1.0)` para (probabilidade media, fracao positiva) |

Validacao sintetica: precision 1.0, recall 1.0, F1 1.0, ROC-AUC 1.0, PR-AUC 1.0, Brier 0.002788951220790531.

Artefato do ultimo treino local (fora do git): `models/artifacts/fraud-risk-v1.joblib`, SHA-256 `7dc0cc4ef95654c4338b55b4a18add8b9928758a006ea04bc0af3f79ece11a3a`. O hash muda se o modelo for retreinado; o registro `.json` ao lado e a fonte de verdade para o carregamento.

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
