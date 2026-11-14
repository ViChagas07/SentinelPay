# ADR 0012: Contracheques guiados por tabelas regulatorias

- Status: aceito
- Data: 2026-11-14

## Contexto
A P08 precisa validar contracheques com regras deterministicas sem ML, LLM, endpoint ou consulta externa. A base oficial de INSS, IRRF, salario minimo e CLT deveria estar em `docs/normas/`, mas o diretorio contem apenas `LEIA-ME.md`. `knowledge/fraud_patterns/holerite.pdf` e `folha_pagamento.pdf` trazem indicadores estruturais e de fraude, mas nao sao documentos oficiais de tabelas legais; o proprio PDF de holerite inclui uma "Tabela INSS 2024" que nao pode ser tratada como fonte oficial.

## Decisao
- Toda aliquota, faixa, teto, salario minimo e parametro de CLT vive em `backend/src/paysentineliq/domain/payslip/data/regulatory/*.yaml`.
- O loader valida esquema, datas, `Decimal` e ordenacao das faixas. Valores monetarios e aliquotas sao strings no YAML para evitar float.
- Cada tabela/valor/parametro tem `fonte`, `vigencia_inicio` e `vigencia_fim`; a regra usa a `fonte` da entrada casada na evidencia.
- Sem tabela/parametro para a competencia, a regra retorna `NOT_VERIFIABLE` (INFO, peso 0). Nunca retorna "fraude" nem aciona o piso critico.
- Os arquivos de producao ficam vazios e com `fonte` explicando a ausencia. A tabela de INSS do PDF de padroes de fraude nao e copiada.
- Regras estruturais e de fraude sao guiadas por `knowledge/fraud_patterns/holerite.pdf` sec. 1/1.2 e `folha_pagamento.pdf` sec. 1.1: campos obrigatorios, somas, liquido, CNPJ/CPF, duplicidade, arredondamento e competencia.
- Testes de calculadores usam tabelas sinteticas em memoria, com `fonte: "tests/fixtures/synthetic"`, apenas para provar o mecanismo. Elas nao sao valores legais e nao vao para os arquivos de producao.
- Dinheiro e `Decimal`; CPF e mascarado na saida; CNPJ/CPF usam o algoritmo deterministico da P07.
- Subscore de risco 0..100, pesos por regra e piso 80 para `net_exceeds_earnings` (liquido maior que proventos). `NOT_VERIFIABLE` nao pontua.
- Rotulos e mensagens ficam em catalogo pt/es/en; a regulacao permanece brasileira.

## Fontes por regra
| Regra | Fonte |
| --- | --- |
| `earnings_total_mismatch` | `knowledge/fraud_patterns/holerite.pdf` sec. 1.2 |
| `deductions_total_mismatch` | `knowledge/fraud_patterns/holerite.pdf` sec. 1.2 |
| `net_mismatch` | `knowledge/fraud_patterns/holerite.pdf` sec. 1.2 |
| `net_exceeds_earnings` | `knowledge/fraud_patterns/folha_pagamento.pdf` sec. 1.1 |
| `inss_mismatch` | `data/regulatory/inss.yaml` (fonte da tabela casada) |
| `irrf_mismatch` | `data/regulatory/irrf.yaml` (fonte da tabela casada) |
| `base_below_minimum` | `data/regulatory/salario_minimo.yaml` (fonte da tabela casada) |
| `overtime_below_minimum` | `data/regulatory/clt.yaml` (parametro `overtime_minimum_percent`) |
| `competency_implausible` | `knowledge/fraud_patterns/holerite.pdf` sec. 1 (periodo de referencia) |
| `employer_cnpj_invalid` | `knowledge/fraud_patterns/holerite.pdf` sec. 1; `folha_pagamento.pdf` sec. 1.1 |
| `employee_cpf_invalid` | `knowledge/fraud_patterns/holerite.pdf` sec. 1; `folha_pagamento.pdf` sec. 1.1 |
| `duplicate_item` | `knowledge/fraud_patterns/holerite.pdf` sec. 1; `folha_pagamento.pdf` sec. 1.1 |
| `rounding_incoherent` | `knowledge/fraud_patterns/holerite.pdf` sec. 1.2; `folha_pagamento.pdf` sec. 1.1 |
| `field_illegible` | `knowledge/fraud_patterns/holerite.pdf` sec. 1 |

## Alternativas descartadas
- **Escrever aliquotas/faixas no codigo:** viola a regra de nao inventar valores legais e impede versionamento por competencia.
- **Usar a tabela INSS 2024 do PDF de padroes de fraude:** o documento nao e oficial e nao esta em `docs/normas/`; seria inventar fonte legal.
- **Desligar toda a validacao de contracheque:** as regras estruturais e de fraude tem fonte e podem ser verificadas agora.
- **Usar ML/LLM para inferir INSS/IRRF:** nao deterministico, sem fonte e fora do escopo.
- **Consultar Receita/INSS/previdencia em API externa:** privacidade, SSRF e escopo; a ausencia fica NAO VERIFICAVEL.

## Consequencias
- As regras de INSS, IRRF, salario minimo e horas extras ficam inativas em producao ate o usuario fornecer as tabelas oficiais. As regras estruturais continuam ativas.
- O mesmo motor funciona quando os YAML forem preenchidos, sem mudar codigo de regra.
- A ausencia de tabela e visivel na saida (`NOT_VERIFIABLE`) e nao eleva o subscore.
- A tabela sintetica de teste e explicitamente um fixture, nao uma fonte legal.
- A lacuna do algoritmo de DV de CPF/CNPJ continua documentada; o indicador "CNPJ/CPF invalido" tem fonte, o algoritmo nao.
- A P11 podera criar `analysis_events` append-only sem PII; nada de Event Sourcing nesta fase.
