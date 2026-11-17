# SPEC 0022: Avaliacao do retrieval em dois estagios (P17.1, ETAPA D)

## Objetivo
Medir, em CPU, a qualidade e a latencia de tres modos de retrieval antes da P18: denso BGE-M3, hibrido RRF e hibrido com rerank. O resultado alimenta `eval/RESULTS.md`, o ADR 0025 e o README publico.

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
- Modo A: embedding denso BGE-M3 e busca densa no `PGVectorHybridStore`.
- Modo B: `HybridRetriever` com RRF e top-K configuravel.
- Modo C: `TwoStageRetriever` sobre o modo B, com reranker e top-N 5 para a metrica.
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
- Tabela A/B/C em `eval/RESULTS.md`.
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

## Fora do escopo
- Benchmark estatistico com centenas de perguntas ou multiplas maquinas.
- Ajuste de pesos/RRF ou troca de modelo.
- Avaliacao do Qwen, do score antifraude ou de respostas finais.
- Correcao do mojibake extraido dos PDFs de `knowledge/`.
- Reindexacao em Pinecone real.

## Riscos e NAO VALIDADO
- 30 perguntas e 21 documentos produzem numeros indicativos, nao um benchmark.
- As conversoes int8 da comunidade usadas no eval sao derivadas dos pesos BAAI, mas nao substituem a validacao do `warmup_models.py` oficial.
- O fallback PyTorch CPU, o `RemoteReranker` real, o Pinecone real e a montagem de modelos no servico `api` seguem NAO VALIDADOS.
- A latencia varia com a maquina, a carga, o comprimento das consultas e o top-K.
- O dataset usa perguntas sem acento; consultas reais acentuadas devem ser incluidas em uma rodada futura.
