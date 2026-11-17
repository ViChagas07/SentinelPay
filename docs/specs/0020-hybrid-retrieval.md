# SPEC 0020: Retrieval hibrido com vetores de 1024d (P17.1, ETAPA B)

## Objetivo
Adicionar o estagio 1 do retrieval em dois estagios: busca densa de 1024 dimensoes do `BAAI/bge-m3` combinada com busca esparsa lexical, atras da flag `HYBRID_RETRIEVAL_ENABLED`. O caminho antigo de embedding de 8 dimensoes e o `KnowledgeRetriever` atual continuam intactos e sao usados quando a flag esta desligada.

A etapa entrega migration, armazenamento PGVector/Pinecone, script de reindexacao idempotente dos 21 documentos de `knowledge/`, cache Redis de embeddings de consulta e o `HybridRetriever` com fusao configuravel. O reranker da ETAPA A nao e aplicado nesta etapa.

## Banco e migration
- Backup logico (`pg_dump`) antes de qualquer migration, com arquivo nao vazio.
- Migration nova `0010_hybrid_retrieval`, sem alterar nem apagar `knowledge_chunks` nem a coluna `embedding vector(8)`.
- Nova tabela `knowledge_hybrid_chunks`:
  - `id`, `document_id` (FK para `knowledge_documents`, cascade), `chunk_index`, `section`, `position`, `content`, `content_hash`, `dense_embedding vector(1024)`, `metadata`, timestamps.
  - Unico por `(document_id, chunk_index)`.
  - Indice HNSW de cosseno em `dense_embedding`.
- Nova tabela `knowledge_hybrid_chunk_sparse_terms`:
  - `chunk_id` (FK para `knowledge_hybrid_chunks`, cascade), `token_id`, `weight`.
  - Unico por `(chunk_id, token_id)` e indice por `token_id`.
- `downgrade` remove somente as tabelas e indices novos; os dados antigos permanecem.

## PGVector e Pinecone
- `PGVectorHybridStore` grava e consulta as tabelas novas; a busca densa usa distancia de cosseno e a esparsa usa produto interno sobre os termos.
- A dimensao densa e fixa em 1024, a dimensao do BGE-M3.
- `PineconeHybridVectorStore` usa vetores densos de 1024 e `sparse_values` nativos; a validacao de producao exige indice com dimensao 1024 e metrica `dotproduct`.
- Criar ou alterar um indice Pinecone existente e operacao externa e NAO VALIDADA nesta etapa; o codigo valida a descricao do indice e falha com erro claro quando dimensao ou metrica divergem.

## Reindexacao
- `scripts/reindex_kb.py` reindexa os 21 documentos de `knowledge/` (8 categorias), reaproveitando `KnowledgeFileSource`, chunks e metadados atuais.
- O script usa o `BgeM3Embedder` local, carrega o modelo uma vez e recusa rodar se o dense ou o esparso nao estiverem carregados.
- Idempotencia: se o `content_hash` do documento e a sequencia de hashes dos chunks novos forem iguais aos ja gravados, o documento e ignorado sem reescrever chunks.
- Reexecucao nao duplica documentos, chunks ou termos esparsos.
- O script nao usa documentos de usuario, nao altera `knowledge/` e nao cai para embedder falso.

## HybridRetriever
- Consulta densa e esparsa sao executadas em paralelo.
- Fusao configuravel por `HYBRID_FUSION=rrf|weighted`:
  - `rrf`: `1/(HYBRID_RRF_K + rank_denso) + 1/(HYBRID_RRF_K + rank_esparso)`.
  - `weighted`: scores normalizados por consulta e combinados por `HYBRID_DENSE_WEIGHT` e `HYBRID_SPARSE_WEIGHT`.
- O resultado tem top-K (`RETRIEVAL_TOP_K`, padrao 25) com score final, score denso, score esparso, ranks e citacao.
- Falha de um dos lados degrada para o outro lado; falha dos dois retorna `rag_unavailable=True`.
- O resultado continua compativel com `RagContextPort`; o caminho antigo nao muda quando a flag esta desligada.

## Cache Redis
- `CachedEmbedder` decora `Embedder` e `SparseEmbedder` com cache de embeddings de consulta.
- Chave e SHA-256 de modelo e texto; o texto bruto da consulta nunca entra na chave, no log ou no valor.
- TTL configuravel por `QUERY_EMBEDDING_CACHE_TTL_SECONDS` (padrao 3600).
- Falha do Redis e fail-open: a consulta segue para o modelo sem derrubar o retrieval.
- Valor corrompido ou de dimensao errada e tratado como miss.

## Configuracao
- `HYBRID_RETRIEVAL_ENABLED` (padrao `false`): mantem o caminho antigo ate a ativacao explicita.
- `HYBRID_FUSION` (padrao `rrf`), `HYBRID_RRF_K` (padrao 60), `HYBRID_DENSE_WEIGHT` (padrao 0.6), `HYBRID_SPARSE_WEIGHT` (padrao 0.4).
- `QUERY_EMBEDDING_CACHE_TTL_SECONDS` (padrao 3600).
- `RETRIEVAL_TOP_K` continua sendo o top-K do estagio 1.

## Criterios de aceite (viram testes)
1. Migration cria as tabelas novas e o downgrade remove apenas elas; `alembic check` fica limpo.
2. Reindexacao de uma fonte sintetica e idempotente na segunda execucao, sem duplicar chunks ou termos.
3. Busca hibrida retorna chunks esperados para consultas em pt, es e en usando fixtures sinteticas.
4. RRF e soma ponderada produzem ordenacao e scores deterministicos.
5. Falha de embedder denso ou esparso degrada para o outro lado; falha dupla retorna `rag_unavailable`.
6. Cache Redis evita chamadas repetidas, valida dimensao, trata cache corrompido e e fail-open.
7. Flag desligada mantem `KnowledgeRetriever` e testes antigos verdes.
8. Ruff, formatacao, mypy strict, import-linter e suite sem Docker verdes.

## Fora do escopo
- Aplicar o reranker `bge-reranker-v2-m3` ou reduzir para top-N 4 nesta etapa.
- Alterar o score antifraude, regras deterministicas ou prompts do Qwen.
- Apagar a tabela antiga, reescrever a migration de 8 dimensoes ou reindexar dados antigos.
- Criar ou redimensionar indices Pinecone reais.
- Baixar modelos ou executar reindexacao real sem os binarios locais.

## Validado nesta etapa
- Migration `0010_hybrid_retrieval` aplicada no Postgres local e no container; `alembic check` sem drift.
- Tabela antiga `knowledge_chunks`, coluna `embedding vector(8)` e teste Docker antigo de PGVector intactos.
- Teste Docker do PGVector hibrido cobre upsert, idempotencia, filtros, busca densa, busca esparsa, reescrita e delete.
- Testes unitarios cobrem RRF, soma ponderada, degradacao, cache Redis, idempotencia da reindexacao e busca sintetica em pt, es e en.
- API reconstruida e saudavel; `/health` continua respondendo com `model_files_missing` porque os binarios BGE nao estao no container.

## Riscos e NAO VALIDADO
- Reindexacao real dos 21 documentos e busca real dependem dos modelos BGE-M3 em `models/retrieval`; sem eles, a execucao fica NAO VALIDADA.
- Pinecone real, dimensao/metrica do indice e busca esparsa nativa ficam NAO VALIDADOS.
- O indice HNSW e a query esparsa em SQL sao validados por teste de integracao Docker quando o banco estiver disponivel.
- A fusao hibrida melhora recall, mas a qualidade depende do chunking e dos pesos; calibracao com consultas reais fica para a proxima etapa.
- O `make test-docker` completo nao foi executado para evitar o roundtrip `downgrade base`; os testes Docker de RAG foram executados isoladamente.
- A ingestao antiga nao atualiza as tabelas hibridas. Depois de mudar `knowledge/`, rode `make reindex-kb` para manter os dois caminhos coerentes.
