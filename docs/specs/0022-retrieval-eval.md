# SPEC 0022: Avaliacao do retrieval em dois estagios (P17.1, ETAPA D)

## Objetivo
Medir, em CPU, a qualidade e a latencia dos modos de retrieval antes da P18. A ETAPA D comparou denso BGE-M3, hibrido RRF e hibrido com rerank. A ETAPA E estendeu a avaliacao para seis modos, incluiu denso com rerank e fusao ponderada 0,7/0,3 e adicionou o benchmark de rerank. O resultado alimenta `eval/RESULTS.md`, o ADR 0025 e o README publico.

## Dataset
- `eval/retrieval_eval.jsonl`, com exatamente 30 perguntas.
- 10 perguntas em portugues, 10 em espanhol e 10 em ingles.
- Dominios: FEBRABAN, INSS, CLT e padroes de fraude.
- Cada item tem `id`, `language`, `domain`, `question` e `expected_documents`.
- Os documentos esperados sao validados contra as chaves reais de `knowledge/` (21 documentos).
- Perguntas e documentos esperados nao sao dados de usuario nem documentos ficticios fora da base existente.

## Script
`scripts/eval_retrieval.py`:
- Carrega BGE-M3 e o reranker local uma vez, em CPU, com backend ONNX int8.
- Reindexacao previa obrigatoria com `scripts/reindex_kb.py`; o script falha se `knowledge_hybrid_chunks` estiver vazio.
- ETAPA D, modo A: embedding denso BGE-M3 e busca densa no `PGVectorHybridStore`.
- ETAPA D, modo B: `HybridRetriever` com RRF e top-K configuravel.
- ETAPA D, modo C: `TwoStageRetriever` sobre o modo B, com reranker e top-N 5 para a metrica.
- ETAPA E, modos D a F: denso com rerank, hibrido ponderado 0,7/0,3 e ponderado com rerank, sem alterar o dataset.
- Aquece os modelos e os caminhos de busca antes de medir.
- Calcula Recall@5 e MRR por pergunta e agrega a media.
- Mede latencia ponta a ponta por consulta e reporta p50 e p95 em milissegundos.
- Coleta exemplos em que o rerank melhora o rank do primeiro documento esperado ou coloca um documento esperado no top-1.
- Grava `eval/RESULTS.md` e `eval/results.json`.
- `--rerank-timeout` permite medir o rerank completo sem o timeout de producao; o padrao usa `RERANK_TIMEOUT_SECONDS`.

## Metricas
- Recall@5: documentos esperados recuperados no top-5 dividido pelo total de documentos esperados, com media sobre as 30 perguntas.
- MRR: reciproco do rank do primeiro documento esperado, com media sobre as 30 perguntas.
- Latencia: tempo de embedding da consulta, busca densa/esparsa, fusao e rerank; exclui carregamento dos modelos.
- A avaliacao e sequencial, sem cache Redis, para isolar o custo dos modelos.

## Resultados esperados
- Tabela de modos em `eval/RESULTS.md`.
- Pelo menos 2 exemplos em que o rerank corrige o estagio 1.
- Limitacoes explicitas sobre tamanho do dataset, conversoes int8 usadas e variacao de CPU.
- Nenhum resultado e inventado; os numeros sao gerados pela execucao real.

## Criterios de aceite
1. Dataset com 30 perguntas, tres idiomas e quatro dominios, com chaves de documentos validas.
2. Script roda de ponta a ponta com os modelos int8 locais e o PGVector reindexado.
3. `eval/RESULTS.md` contem tabela, configuracao, exemplos e limitacoes.
4. `eval/results.json` contem os agregados e os exemplos.
5. ADR 0025 justifica bi-encoder, cross-encoder, v2-m3 multilíngue e CPU/ONNX int8.
6. `make eval-retrieval` e `make check` verdes.
7. ETAPA E: os seis modos e o benchmark de rerank rodam sem alterar o dataset.

## Extensao ETAPA E (executada)
- `models/` montado como somente leitura no servico `api`; `/health` do container com `loaded=true` para embedder, sparse embedder e reranker.
- `repair_text` com `ftfy`, NFC e normalizacao de travessoes; reindexacao idempotente com 53 chunks reescritos e 56 no total, 0 `U+FFFD`, 0 `U+2014` e 0 `U+2013`.
- Eval com denso, denso+rerank, RRF, ponderado 0,7/0,3, RRF+rerank e ponderado+rerank.
- Benchmark de 18 configuracoes variando K 10/15/25, max_length 256/384/512 e int8/fp32; padrao int8, K=25 e max_length=512.
- Secao "Limitacoes e nao validado" em `eval/RESULTS.md`.

## Fora do escopo
- Benchmark estatistico com centenas de perguntas ou multiplas maquinas.
- Calibracao fina de pesos alem do teste 0,7/0,3 ou troca de modelo.
- Avaliacao do Qwen, do score antifraude ou de respostas finais.
- Reindexacao em Pinecone real.

## Riscos e NAO VALIDADO
- 30 perguntas e 21 documentos produzem numeros indicativos, nao um benchmark.
- As conversoes int8 da comunidade usadas no eval sao derivadas dos pesos BAAI, mas nao substituem a validacao do `warmup_models.py` oficial.
- O fallback PyTorch CPU, o `RemoteReranker` real e o Pinecone real seguem NAO VALIDADOS; a montagem de modelos no servico `api` foi validada na ETAPA E.
- O benchmark de latencia usa 3 consultas e nao substitui uma medicao maior.
- A latencia varia com a maquina, a carga, o comprimento das consultas e o top-K.
- O dataset usa perguntas sem acento; consultas reais acentuadas devem ser incluidas em uma rodada futura.
