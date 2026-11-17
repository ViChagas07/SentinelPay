# ADR 0022: Retrieval em dois estagios com BGE-M3 e reranker local

- Status: aceito
- Data: 2026-11-17

## Contexto
A P10 entregou RAG com embeddings OpenAI-compatible e PGVector, sem hybrid search e sem reranking neural. A proxima fase precisa de retrieval em dois estagios: `BAAI/bge-m3` para embedding denso de 1024 dimensoes e pesos esparsos, seguido de `BAAI/bge-reranker-v2-m3` como cross-encoder, reduzindo os candidatos antes do Qwen. O ambiente nao tem GPU e a regra do projeto proibe CUDA, ROCm e DirectML.

## Decisao
- Criar as portas `Embedder`, `SparseEmbedder` e `Reranker` em `domain/ports/retrieval.py`, com value objects `SparseVector`, `RerankResult`, `ModelStatus` e `RetrievalStatus`.
- Implementar adaptadores locais em `infrastructure/retrieval`, com ONNX Runtime int8 como caminho padrao e PyTorch CPU como fallback.
- Fixar `CPUExecutionProvider` no ONNX Runtime; nao existe selecao de GPU nesta fase.
- Usar o ONNX oficial de `BAAI/bge-m3` como encoder, calcular o denso pelo token CLS normalizado e o esparso por `relu(hidden @ sparse_weight + bias)` com mascara de atencao.
- Usar o ONNX exportado do `BAAI/bge-reranker-v2-m3` como cross-encoder, com score sigmoide do logit.
- Carregar os modelos uma unica vez no lifespan do FastAPI, em `asyncio.to_thread`, e expor o estado no `/health`. Requisicoes nunca carregam pesos.
- Configurar top-K, top-N, habilitacao do reranker, backends, comprimento maximo, lote e threads por ambiente.
- Entregar `scripts/warmup_models.py` para baixar, converter e quantizar os modelos; os binarios ficam em `models/retrieval` e fora do git.

## Alternativas consideradas
- **FlagEmbedding ou sentence-transformers em PyTorch puro:** simples, mas nao atende ao requisito de int8/ONNX e tende a consumir mais memoria em CPU.
- **API remota de embeddings/reranking:** adiciona dependencia de rede, custo e latencia; contraria o requisito de execucao local.
- **Um unico modelo denso sem esparso:** perde a busca lexical que motivou o BGE-M3 hibrido.
- **Carregar modelos por requisicao:** inviabiliza latencia e memoria; proibido pela fase.
- **Mover todas as portas legadas para o dominio:** refatoracao fora do escopo e sem ganho para esta etapa; as portas novas ficam no dominio e as antigas permanecem onde estao.

## Consequencias
- A aplicacao sobe mesmo sem os modelos, mas o `/health` mostra `loaded=false` e um codigo de erro; a degradacao futura do retrieval deve usar esse estado.
- O primeiro startup com modelos presentes fica mais lento e consome mais memoria; a carga e unica e acontece antes de aceitar requisicoes.
- O fallback PyTorch depende de `torch` e `transformers` instalados; sem eles, somente o backend ONNX funciona.
- O download e a quantizacao reais nao foram executados nesta etapa. O script e os adaptadores existem, mas o formato final do ONNX e o desempenho em CPU permanecem NAO VALIDADOS.
- A integracao do retrieval hibrido com PGVector, a fusao de scores e o uso pelo Qwen ficam para as etapas seguintes.
