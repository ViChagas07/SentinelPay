# Resultados da avaliacao de retrieval

Avaliacao local em CPU dos tres modos de retrieval planejados na P17.1.

## Configuracao

- Data: 2026-11-17 02:23 UTC
- Dataset: `eval/retrieval_eval.jsonl` (30 perguntas)
- Idiomas: pt=10, es=10, en=10
- Dominios: febraban=13, inss=6, clt=6, fraud=5
- Top-K do estagio 1: 25
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
| Denso (BGE-M3) | 0.9333 | 0.8917 | 80.19 | 87.17 |
| Hibrido (RRF) | 0.8667 | 0.8011 | 84.21 | 91.96 |
| Hibrido + rerank | 0.9667 | 0.9583 | 12076.74 | 13440.36 |

## Exemplos em que o rerank corrige o estagio 1

### Exemplo 1: pt-febraban-01 (pt)

Pergunta: Qual e o tamanho da linha digitavel de um boleto bancario e quantos digitos tem o codigo de barras?

Documentos esperados: febraban/manual_febraban_v1.pdf

Estagio 1: top1=`glossary/glossary.pdf` (rank esperado=2, score=0.0328)

Depois do rerank: top1=`febraban/manual_febraban_v1.pdf` (rank esperado=1, score=0.9993)

Antes: de 4 dígitos representando os dias corridos desde 07/10/1997. Usado para calcular a data de vencimento a partir do código de barras. Código de Barras Representação gráfica dos 44 dígitos do boleto em barras verticais (padrão Interleaved 2 of 5). Lido por scanners nos bancos. Linha Digitável Represen

Depois: ira / Modalidade Tipo de cobrança bancária MÉDIO Instrução de Cobrança Juros, multa, desconto, protesto MÉDIO 1.2 Linha Digitável, Estrutura Completa A linha digitável é a representação numérica do código de barras. Deve ter exatamente 47 dígitos (boleto comum) ou 48 dígitos (boleto de tributos/gui

### Exemplo 2: pt-fraud-01 (pt)

Pergunta: Quais codigos de banco inexistentes indicam boleto falso?

Documentos esperados: fraud_patterns/banco_inexistente.pdf, bacen/instituicoes.pdf

Estagio 1: top1=`faq/antifraud_faq.pdf` (rank esperado=2, score=0.0323)

Depois do rerank: top1=`fraud_patterns/banco_inexistente.pdf` (rank esperado=1, score=0.9779)

Antes: FAQ Antifraude, Perguntas e Respostas Técnicas Base de conh P01: Multa de 5% ao dia é válida em boleto? R: NÃO. A legislação brasileira limita a multa de mora a 2% sobre o valor (Art. 52 do CDC e jurisprudência do STJ). Juros máximos: 1% ao mês (taxa Selic). Boleto com multa de 5% ao dia é ilegal e

Depois: 0 Banco Inexistente / Código Inválido Identificação 1. Códigos de Banco Fraudulentos Mais Comuns Boletos fraudulentos frequentemente usam códigos de banco inválidos, seja por descuido do fraudador ou para dificultar a verificação manual. Código Situação 000 Código nulo, banco inexistente 999 Código

### Exemplo 3: es-inss-02 (es)

Pergunta: Que indicadores de fraude aparecen cuando el FGTS o el INSS no se recolle en la nomina?

Documentos esperados: fraud_patterns/folha_pagamento.pdf

Estagio 1: top1=`glossary/glossary.pdf` (rank esperado=None, score=0.0317)

Depois do rerank: top1=`fraud_patterns/folha_pagamento.pdf` (rank esperado=1, score=0.7987)

Antes: lerite. FGTS Fundo de Garantia por Tempo de Serviço. Encargo patronal de 8% do salário bruto. Não é descontado do empregado, é custo da empresa. INSS Instituto Nacional do Seguro Social. Desconto obrigatório do empregado calculado progressivamente sobre o salário. IRRF Imposto de Renda Retido na Fo

Depois: 0 Fraude em Folha de Pagamento Padrões de adulte 1. Modalidades de Fraude em Folha Modalidade Descrição Risco Funcionário Fantasma Inclusão de empregado inexistente na folha para desvio do salário. CRÍTICO Salário Inflado Salário real é X, mas folha registra X + Y para desviar a diferença Y. CRÍTICO

## Como reproduzir

```powershell
poetry -C backend run python ../scripts/reindex_kb.py --env-file ../.env.example --knowledge-root ../knowledge
poetry -C backend run python ../scripts/eval_retrieval.py
```

## Limitacoes

- 30 perguntas e 21 documentos: os numeros sao indicativos, nao um benchmark estatistico.
- Os modelos usados sao conversoes int8 da comunidade para ONNX (`onnx-community/bge-m3-ONNX` e `onnx-community/bge-reranker-v2-m3-ONNX`), com os pesos BAAI e o `sparse_linear.pt` oficial.
- A avaliacao usa top-N 5 para calcular Recall@5; a producao entrega top-N 4 ao Qwen.
- Latencia de CPU varia com a maquina, carga do sistema e comprimento das consultas.
- O dataset cobre FEBRABAN, INSS, CLT e padroes de fraude, mas nao substitui uma avaliacao com analistas e consultas reais de producao.
