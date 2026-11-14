# SPEC 0009: Contracheques deterministicos (INSS, IRRF e CLT)

## Objetivo
Extrair e validar contracheques de forma deterministica, com dinheiro em `Decimal` e regras 100% guiadas por tabelas regulatorias versionadas. Valores legais nunca sao escritos no codigo nem em testes como se fossem lei.

## Fontes e politica de dados
- Fontes oficiais previstas: `docs/normas/` (tabelas de INSS, IRRF, salario minimo e trechos da CLT por competencia).
- Estado atual: `docs/normas/` contem apenas `LEIA-ME.md`; nenhuma tabela oficial foi fornecida.
- Arquivos de dados: `backend/src/paysentineliq/domain/payslip/data/regulatory/{inss,irrf,salario_minimo,clt}.yaml`, com `versao`, `fonte`, `vigencia_inicio`, `vigencia_fim`, `tabelas`/`valores`/`parametros`.
- Com a base oficial ausente, os arquivos ficam com listas vazias e `fonte` marcando NAO VERIFICAVEL. As regras que dependem deles retornam NAO VERIFICAVEL, com peso 0, e nunca "fraude" ou risco alto.
- `knowledge/fraud_patterns/holerite.pdf` e `knowledge/fraud_patterns/folha_pagamento.pdf` sao fontes para regras estruturais e indicadores de fraude (campos obrigatorios, somas, liquido, CNPJ/CPF, duplicidade, arredondamento), nao para aliquotas, faixas, teto ou salario minimo.
- A tabela "INSS 2024" que aparece em `knowledge/fraud_patterns/holerite.pdf` NAO e usada como tabela legal: ela nao esta em `docs/normas/` e nao e documento oficial.
- Testes usam tabelas sinteticas em memoria, rotuladas como `tests/fixtures/synthetic`, apenas para exercitar os calculadores. Elas nao representam a lei.

## Escopo
- Dominio puro `Payslip` (empregador, CNPJ, funcionario, CPF mascarado, competencia, itens de provento/desconto, totais, liquido).
- Extracao de texto OCR tolerante a layouts, com confianca por campo; layout desconhecido reduz confianca, nao gera erro.
- Regras iniciais com id, versao, severidade, peso, fonte e evidencia:
  - soma dos proventos e dos descontos coerente com os totais;
  - liquido = proventos - descontos;
  - INSS compativel com a tabela da competencia;
  - IRRF compativel com a tabela;
  - salario base nao abaixo do minimo vigente quando aplicavel;
  - adicional de horas extras nao abaixo do minimo citado na fonte;
  - competencia plausivel;
  - CNPJ e CPF com DV valido;
  - itens duplicados ou arredondamentos incoerentes.
- Saida `PayslipAnalysis` com campos e confianca, evidencias (chave i18n) e subscore deterministico.
- Rotulos e mensagens em pt, es e en; a regulacao e apenas brasileira.

## Fora do escopo
- ML, LLM, endpoint, persistencia, fila ou consulta externa.
- Calculo de FGTS, contribuicao sindical, pensao, beneficios, ferias, 13o, rescisao e pro-labore.
- Validar CBO/CNAE, data de admissao, assinatura digital, autenticidade do emissor ou registro em sistema oficial.
- Criar tabela `analysis_events` (P11) ou qualquer Event Sourcing.

## Contratos de dominio
- `YearMonth(year, month)`: competencia valida; `first_day`.
- `PayslipItem`: `description`, `kind` (`earning`, `deduction`, `info`, `unknown`), `category` (`base_salary`, `overtime`, `inss`, `irrf`, `other`), `amount: Decimal`, `overtime_percent: Decimal | None`, `confidence`.
- `Payslip`: `employer_name`, `employer_cnpj: Cnpj | None`, `employee_name`, `employee_cpf_masked`, `employee_cpf_valid: bool | None`, `competency`, `items`, `total_earnings`, `total_deductions`, `net`, `irrf_base`, `dependents`.
- `Cnpj`/`Cpf` reutilizam o algoritmo deterministico da P07; o CPF e mascarado na saida.
- `PayslipExtraction`: campos com `ExtractedField[T]` (valor, confianca, raw), incluindo itens, totais, competencia, nomes, CNPJ, CPF, base IRRF e dependentes.
- `RegulatoryTables`: carrega INSS, IRRF, salario minimo e parametros de CLT; lookup por competencia; ausencia retorna `None`.

## Regras e fontes
- Estruturais e de fraude: `knowledge/fraud_patterns/holerite.pdf` sec. 1, 1.2 e `knowledge/fraud_patterns/folha_pagamento.pdf` sec. 1.1.
- DVs de CNPJ/CPF: fonte do indicador nos mesmos documentos; o algoritmo de DV nao consta nessas fontes (mesma lacuna registrada na P07).
- INSS: `data/regulatory/inss.yaml`; a evidencia usa a `fonte` da tabela casada.
- IRRF: `data/regulatory/irrf.yaml`.
- Salario minimo: `data/regulatory/salario_minimo.yaml`.
- Horas extras: `data/regulatory/clt.yaml` (parametro `overtime_minimum_percent`).
- Regra sem fonte registrada nao entra no motor.
- Ausencia de tabela/parametro para a competencia gera evidencia `NOT_VERIFIABLE` (INFO, peso 0) e nao altera o subscore.

## Score
- Risco 0..100: `min(100, soma dos pesos das regras disparadas)`.
- Regras criticas impoem piso 80; `net_exceeds_earnings` e critica.
- Evidencias sao ordenadas por `rule_id` e depois por detalhe.
- Evidencia NAO VERIFICAVEL nao conta peso e nao aciona piso.

## Criterios de aceite (viram testes)
1. Loader aceita YAML valido, converte dinheiro para `Decimal`, valida datas/faixas e rejeita esquema invalido.
2. Loader padrao carrega os quatro arquivos vazios e expoe a marca NAO VERIFICAVEL.
3. Contracheque sintetico valido, com tabelas sinteticas, pontua 0 e nao tem evidencia de risco.
4. Contracheque sintetico valido, sem tabelas oficiais, pontua 0; INSS/IRRF/minimo/horas extras sao NAO VERIFICAVEIS, nunca alto risco.
5. Cada adulteracao isolada dispara a regra esperada: total de proventos, total de descontos, liquido, liquido maior que proventos, INSS, IRRF, salario minimo, horas extras, competencia, CNPJ, CPF, item duplicado, arredondamento e campo ilegivel.
6. Todos os `message_key` usados nas evidencias existem em pt, es e en.
7. CPF nao aparece completo em `PayslipAnalysis`; evidencias usam mascara.
8. `make check` fica verde (Ruff, format, mypy strict, import-linter e testes sem Docker).

## Plano de testes
1. Loader e esquema.
2. Modelos e extracao OCR (layout conhecido, layout desconhecido, confusoes 0/O e 1/l, campos ausentes).
3. Calculadores regulatorios com tabelas sinteticas.
4. Motor de regras: valido com tabelas, valido sem tabelas, uma adulteracao por caso, piso critico e cap.
5. i18n: catalogo completo nos tres idiomas.
6. `make check`.

## Riscos e NAO VALIDADO
- Sem tabelas oficiais, as regras de INSS/IRRF/minimo/horas extras ficam inativas em producao; isso e intencional e sinalizado.
- A tabela de INSS do PDF de padroes de fraude nao foi usada por nao ser fonte oficial em `docs/normas/`.
- O algoritmo de DV de CPF/CNPJ nao consta nas fontes; usa o algoritmo deterministico da P07 e a lacuna fica registrada.
- A classificacao de itens por descricao e heuristica; layout desconhecido reduz confianca e pode deixar a soma NAO VERIFICAVEL.
- O calculo de IRRF usa a base IRRF extraida quando existir; sem base e sem dados suficientes, a regra pode ficar NAO VERIFICAVEL.
- Arredondamento oficial de INSS/IRRF nao consta nas fontes; a comparacao aceita tolerancia de 0,01 e sinaliza valores com mais de duas casas.
- A regulacao e brasileira; traducoes pt/es/en sao de interface, nao mudam a lei aplicavel.
