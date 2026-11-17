# Resultados da avaliacao de retrieval

Avaliacao local em CPU dos seis modos de retrieval planejados na P17.1.

## Configuracao

- Data: 2026-11-17 04:12 UTC
- Dataset: `eval/retrieval_eval.jsonl` (30 perguntas)
- Idiomas: pt=10, es=10, en=10
- Dominios: febraban=13, inss=6, clt=6, fraud=5
- Top-K do estagio 1: 25
- Fusao ponderada: dense=0.7, sparse=0.3
- K da metrica: 5 (Recall@5 e MRR)
- Top-N do reranker na avaliacao: 5 (producao usa RERANK_TOP_N=4)
- Timeout do reranker: 30 s
- Backend: ONNX Runtime int8 em CPU (onnx)
- Host: Windows-10-10.0.26200-SP0 / 16 vCPUs
- Modelos: models\retrieval
- Latencia inclui embedding da consulta, busca, fusao e rerank; nao inclui carga dos modelos.
- Execucao sequencial, sem cache de consulta e sem paralelismo entre queries.

## Tabela

| Modo | Recall@5 | MRR | p50 (ms) | p95 (ms) |
| --- | ---: | ---: | ---: | ---: |
| Denso (BGE-M3) | 0.9333 | 0.8917 | 90.11 | 96.16 |
| Denso + rerank | 0.9667 | 0.9611 | 14244.38 | 15180.27 |
| Hibrido RRF | 0.8667 | 0.8011 | 84.40 | 457.67 |
| Hibrido ponderado 0.7/0.3 | 0.8667 | 0.8344 | 84.54 | 92.34 |
| Hibrido RRF + rerank | 0.9667 | 0.9417 | 12814.01 | 14333.89 |
| Hibrido ponderado + rerank | 0.9667 | 0.9583 | 13015.21 | 13580.81 |

## Exemplos em que o rerank corrige o estagio 1

### Exemplo 1: en-clt-01 (en)

Pergunta: What are common indicators of a forged payslip under CLT rules?

Documentos esperados: fraud_patterns/holerite.pdf, fraud_patterns/folha_pagamento.pdf

Estagio 1 (Denso (BGE-M3)): top1=`fraud_patterns/boleto_falso.pdf` (rank esperado=2, score=0.5116)

Depois (Denso + rerank): top1=`fraud_patterns/folha_pagamento.pdf` (rank esperado=1, score=0.0394)

Antes: i o PDF antes de reencaminhar. CRÍTICO Boleto de Segunda Via Falsa Site falso simula portal do fornecedor/banco. Emite 'segunda via' fraudulenta. ALTO 1.2 Indicadores de Fraude, Checklist [CRÍTICO] DAC da linha digitável não confere matematicamente [CRÍTICO] Banco emissor (3 primeiros dígitos) não e

Depois: 0 Fraude em Folha de Pagamento Padrões de adulte 1. Modalidades de Fraude em Folha Modalidade Descrição Risco Funcionário Fantasma Inclusão de empregado inexistente na folha para desvio do salário. CRÍTICO Salário Inflado Salário real é X, mas folha registra X + Y para desviar a diferença Y. CRÍTICO

### Exemplo 2: en-clt-02 (en)

Pergunta: How can ghost employees and inflated salaries be detected in payroll?

Documentos esperados: fraud_patterns/folha_pagamento.pdf

Estagio 1 (Hibrido RRF): top1=`glossary/glossary.pdf` (rank esperado=None, score=0.0296)

Depois (Hibrido RRF + rerank): top1=`fraud_patterns/folha_pagamento.pdf` (rank esperado=1, score=0.0321)

Antes: Sacado Avalista Coobrigado no boleto. Pessoa que garante o pagamento junto ao sacado principal. Nosso Número Composto Formato do nosso número que inclui prefixo da carteira + número sequencial + dígito verificador. Campo Livre Posições 20 a 44 do código de barras. Definido por cada banco conforme co

Depois: 0 Fraude em Folha de Pagamento Padrões de adulte 1. Modalidades de Fraude em Folha Modalidade Descrição Risco Funcionário Fantasma Inclusão de empregado inexistente na folha para desvio do salário. CRÍTICO Salário Inflado Salário real é X, mas folha registra X + Y para desviar a diferença Y. CRÍTICO

### Exemplo 3: es-clt-01 (es)

Pergunta: Que datos del empleador y del empleado son obligatorios en el recibo de nomina?

Documentos esperados: fraud_patterns/holerite.pdf

Estagio 1 (Denso (BGE-M3)): top1=`bacen/boletos.pdf` (rank esperado=None, score=0.4567)

Depois (Denso + rerank): top1=`fraud_patterns/holerite.pdf` (rank esperado=1, score=0.0041)

Antes: elIQ v1.0 Regulação BACEN, Boletos e Cobrança Normas de regi 1. Registro Obrigatório de Boletos (desde 2018) Desde novembro de 2018 (Resolução BACEN 4.569/2017), TODOS os boletos de cobrança devem ser registrados na CIP, Câmara Interbancária de Pagamentos. Boletos não registrados são recusados pelos

Depois: 0 Holerite / Contracheque, Validação Técnica Estrutura, campo 1. Campos Obrigatórios do Holerite (CLT, Art. 464) Campo Conteúdo Prioridade Identificação do Empregador Razão social, CNPJ, endereço CRÍTICO Identificação do Empregado Nome, CPF, matrícula, cargo, CBO, departamento CRÍTICO Período de Ref

## Como reproduzir

```powershell
poetry -C backend run python ../scripts/reindex_kb.py --env-file ../.env.example --knowledge-root ../knowledge
poetry -C backend run python ../scripts/eval_retrieval.py
```

<!-- rerank-benchmark:start -->
## Benchmark de rerank (K, max_length, precisao)

Consultas medidas: 3. Latencia medida apenas no rerank, com candidatos do estagio 1 (RRF, top-25), em CPU.

### Recall de candidatos do estagio 1

| K | Recall de candidatos |
| ---: | ---: |
| 10 | 0.9667 |
| 15 | 0.9667 |
| 25 | 1.0000 |

### Cobertura de tokens por max_length

| max_length | Pares sem truncamento |
| ---: | ---: |
| 256 | 0.3093 |
| 384 | 0.9760 |
| 512 | 1.0000 |

### Latencia por configuracao

| Precisao | max_length | K | p50 (ms) | p95 (ms) |
| --- | ---: | ---: | ---: | ---: |
| int8 | 256 | 10 | 3057.40 | 3240.86 |
| int8 | 256 | 15 | 4662.27 | 4734.13 |
| int8 | 256 | 25 | 7438.86 | 7613.03 |
| int8 | 384 | 10 | 5372.14 | 5450.14 |
| int8 | 384 | 15 | 8233.79 | 8236.63 |
| int8 | 384 | 25 | 13220.49 | 13611.19 |
| int8 | 512 | 10 | 5243.28 | 5492.58 |
| int8 | 512 | 15 | 7789.96 | 7963.98 |
| int8 | 512 | 25 | 12570.10 | 13233.90 |
| fp32 | 256 | 10 | 5676.40 | 5799.71 |
| fp32 | 256 | 15 | 8317.37 | 8937.51 |
| fp32 | 256 | 25 | 13340.81 | 13808.34 |
| fp32 | 384 | 10 | 8532.07 | 8655.26 |
| fp32 | 384 | 15 | 12745.82 | 12944.89 |
| fp32 | 384 | 25 | 20591.50 | 21251.51 |
| fp32 | 512 | 10 | 8912.72 | 8958.69 |
| fp32 | 512 | 15 | 13065.44 | 13387.07 |
| fp32 | 512 | 25 | 21066.99 | 21939.29 |

### Recomendacao

**int8, K=25, max_length=512**: p50 12570.10 ms, p95 13233.90 ms. int8 pelo custo e pela regra de CPU; K escolhido como o menor com recall de candidatos a no maximo 1 ponto do melhor; entre os max_length com cobertura de tokens >= 95%, escolhido o de menor p50 (512).

<!-- rerank-benchmark:end -->
## Limitacoes e nao validado

- 30 perguntas e 21 documentos: os numeros sao indicativos, nao um benchmark estatistico.
- Os modelos usados sao conversoes int8 da comunidade para ONNX (`onnx-community/bge-m3-ONNX` e `onnx-community/bge-reranker-v2-m3-ONNX`), com os pesos BAAI e o `sparse_linear.pt` oficial.
- A conversao oficial pelo `warmup_models.py` e o fallback PyTorch CPU nao foram exercitados neste eval.
- O benchmark de latencia usa 3 consultas; p50/p95 sao indicativos e nao substituem uma medicao maior.
- O modelo fp32 do benchmark e uma conversao da comunidade; o caminho oficial fp32/quantizacao propria NAO VALIDADO.
- A escolha de max_length usa cobertura de tokens; a qualidade por max_length nao foi reavaliada individualmente.
- Pinecone real com dimensao 1024 e metrica `dotproduct` NAO VALIDADO.
- `RemoteReranker` real, autenticacao e disponibilidade do provedor NAO VALIDADOS.
- A avaliacao usa top-N 5 para calcular Recall@5; a producao entrega top-N 4 ao Qwen.
- Latencia de CPU varia com a maquina, carga do sistema e comprimento das consultas.
- O dataset cobre FEBRABAN, INSS, CLT e padroes de fraude, mas nao substitui uma avaliacao com analistas e consultas reais de producao.
