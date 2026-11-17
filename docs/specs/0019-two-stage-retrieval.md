# SPEC 0019: Retrieval em dois estagios (P17.1, ETAPA A)

## Objetivo
Preparar a base do retrieval em dois estagios do SentinelPay sem alterar o pipeline de analise ainda. O estagio 1 usa `BAAI/bge-m3` para embedding denso de 1024 dimensoes e pesos esparsos (lexicais); o estagio 2 usa `BAAI/bge-reranker-v2-m3` como cross-encoder. Tudo roda em CPU, com ONNX Runtime int8 e fallback PyTorch CPU.

Esta etapa entrega somente portas, adaptadores locais, configuracao, carregamento unico no lifespan, estado no `/health` e o script de warmup dos modelos. A recuperacao hibrida e o uso pelo Qwen ficam para as etapas seguintes.

## Portas
- `Embedder`: embedding denso, com `dimension`, `model_id` e `embed(texts)`.
- `SparseEmbedder`: pesos lexicais por token, com `model_id` e `embed_sparse(texts)`.
- `Reranker`: reranking de pares consulta/documento, com `model_id` e `rerank(query, documents, top_n)`.
- `SparseVector` e `RerankResult` sao value objects das portas.
- `RetrievalStatus` e `ModelStatus` descrevem o estado exposto no `/health`.
- As novas portas ficam em `domain/ports/retrieval.py`. As portas legadas de embedding continuam em `application/ports` para nao refatorar a ingestao da P10.

## Adaptadores
- `BgeM3Embedder` implementa `Embedder` e `SparseEmbedder`.
  - ONNX int8: `model_int8.onnx` (preferido) ou `model.onnx`, com `tokenizer.json` e `sparse_linear.npy`.
  - PyTorch CPU: `AutoModel` local com os arquivos do modelo e o mesmo `sparse_linear.npy`.
  - Denso: CLS token (`last_hidden_state[:, 0]`) normalizado em L2, 1024 dimensoes.
  - Esparso: `relu(last_hidden_state @ peso + bias)`, mascarado pelo `attention_mask`; tokens repetidos ficam com o maior peso.
  - Inferencia fora do event loop (`asyncio.to_thread`) e em lotes de `BATCH_SIZE`.
  - Nunca carrega pesos por requisicao. O runtime chama `load()` uma vez no startup.
- `BgeRerankerV2M3` implementa `Reranker`.
  - ONNX int8: `model_int8.onnx` (preferido) ou `model.onnx`, com `tokenizer.json`.
  - PyTorch CPU: `AutoModelForSequenceClassification` local.
  - Pares truncados por `RERANK_MAX_LENGTH`; score final e sigmoide do logit.
  - Resultado ordenado por score decrescente e desempate pelo indice original.
- Os adaptadores usam somente `CPUExecutionProvider` no ONNX Runtime e nunca habilitam CUDA, ROCm ou DirectML.
- `TORCH_NUM_THREADS` (quando maior que zero) chama `torch.set_num_threads` antes da carga do modelo PyTorch.
- Falha de arquivo, pacote ou carga vira codigo estavel de erro (`model_files_missing`, `onnxruntime_unavailable`, `tokenizer_unavailable`, `pytorch_unavailable`, `model_load_failed`) sem derrubar o processo.

## Configuracao por ambiente
- `RETRIEVAL_MODEL_DIR` (padrao `models/retrieval`): raiz dos modelos locais.
- `RETRIEVAL_TOP_K` (padrao 25): candidatos do estagio 1.
- `RERANK_TOP_N` (padrao 4): documentos entregues ao Qwen; deve ser menor ou igual a `RETRIEVAL_TOP_K`.
- `RERANK_ENABLED` (padrao `true`): liga ou desliga o estagio 2.
- `EMBEDDER_BACKEND` (`onnx` ou `pytorch`, padrao `onnx`).
- `RERANKER_BACKEND` (`onnx` ou `pytorch`, padrao `onnx`).
- `RERANK_MAX_LENGTH` (padrao 512): truncamento dos pares do reranker.
- `BATCH_SIZE` (padrao 16): lote dos adaptadores locais.
- `TORCH_NUM_THREADS` (padrao 0): 0 deixa o PyTorch escolher; valor positivo fixa as threads.

## Carregamento e health
- `create_app` cria um unico `RetrievalRuntime` e o guarda em `app.state.retrieval_runtime`; a carga acontece no lifespan, uma vez, em thread separada.
- Se os arquivos nao existirem, o app sobe normalmente e o estado fica `loaded=false` com erro estavel.
- `RERANK_ENABLED=false` cria o runtime sem reranker e nao carrega o modelo do estagio 2.
- `/health` continua `200` e passa a expor `retrieval` com `top_k`, `rerank_top_n`, `rerank_enabled`, `embedder`, `sparse_embedder` e `reranker`.
- Nenhum caminho de arquivo, segredo ou dado pessoal aparece no `/health`; apenas `model`, `backend`, `loaded` e `error`.

## Warmup
- `scripts/warmup_models.py` baixa os arquivos de `BAAI/bge-m3` e `BAAI/bge-reranker-v2-m3` do Hugging Face e prepara o diretorio local.
- Para o embedder, baixa o ONNX oficial, quantiza dinamicamente para int8 e converte `sparse_linear.pt` em `sparse_linear.npy` sem executar pickle arbitrario.
- Para o reranker, exporta o cross-encoder para ONNX e quantiza para int8 quando `torch`, `transformers` e `onnx` estiverem disponiveis.
- O script e idempotente, aceita `--output-dir`, `--backend`, `--force`, `--skip-embedder` e `--skip-reranker`, e falha com mensagem clara quando uma dependencia de conversao falta.
- Modelos ficam fora do git.

## Criterios de aceite (viram testes)
1. As tres portas e os value objects rejeitam entradas invalidas.
2. Um runtime falso carrega uma unica vez, mesmo com chamadas repetidas, e nao carrega durante requisicoes.
3. O lifespan chama a carga uma unica vez; o `/health` continua `200` e mostra o estado dos modelos.
4. `RERANK_ENABLED=false` nao carrega nem exibe reranker carregado.
5. Arquivos ausentes viram estado de erro, sem excecao no startup.
6. A matematica densa/esparsa e o ranking do reranker sao deterministas nos testes unitarios.
7. Configuracao invalida (`top_n > top_k`, backend desconhecido, lote nao positivo) e recusada.
8. Ruff, formatacao, mypy strict, import-linter e suite sem Docker continuam verdes.

## Fora do escopo
- Integrar o retrieval hibrido ao `KnowledgeRetriever`, ao PGVector ou ao grafo LangGraph.
- Alterar a migration `vector(8)` ou reindexar a base.
- Usar o Qwen, montar prompt ou alterar o score.
- Baixar ou versionar os modelos neste repositorio.
- Alterar Docker Compose, volumes, banco ou knowledge base.

## Riscos e NAO VALIDADO
- O download, a quantizacao int8 e a exportacao real do reranker nao foram executados nesta etapa; ficam NAO VALIDADOS.
- O nome do output ONNX e o formato dos arquivos externos podem variar; o adaptador prefere `token_embeddings`/`last_hidden_state` (3D) e `logits` (2D), aceita o primeiro output com a dimensionalidade esperada e falha com erro estavel caso o contrato mude.
- O modelo ONNX oficial do BGE-M3 e grande (aprox. 2,2 GB) e a quantizacao exige memoria; a execucao em maquina com pouca RAM fica NAO VALIDADA.
- O fallback PyTorch exige `torch` e `transformers` instalados no ambiente; sem eles, o backend `pytorch` fica indisponivel com erro estavel.
- Desempenho de CPU, latencia e memoria dos modelos reais ficam NAO VALIDADOS.
