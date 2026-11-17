# ADR 0023: Armazenamento e busca hibrida de 1024 dimensoes

- Status: aceito
- Data: 2026-11-17

## Contexto
A P10 indexou `knowledge/` com `EmbeddingPort` e uma coluna `vector(EMBEDDING_DIM)` de 8 dimensoes no ambiente local. A ETAPA A adicionou `BAAI/bge-m3` local, com embedding denso de 1024 dimensoes e pesos esparsos, alem do reranker para uma etapa futura. A ETAPA B precisa colocar o estagio 1 em producao atras de uma flag sem quebrar o caminho antigo.

## Decisao
- Criar tabelas paralelas `knowledge_hybrid_chunks` e `knowledge_hybrid_chunk_sparse_terms`, em vez de alterar a tabela antiga. Os documentos continuam em `knowledge_documents`.
- Guardar o vetor denso de 1024 dimensoes na tabela nova, com indice HNSW de cosseno.
- Guardar o vetor esparso como termos `(chunk_id, token_id, weight)`, com indice por `token_id`, para calcular o produto interno em SQL.
- Manter `knowledge_chunks` e a coluna `embedding vector(8)` intactas. A flag `HYBRID_RETRIEVAL_ENABLED` escolhe o caminho.
- Implementar `HybridRetriever` na camada de aplicacao, com fusao RRF ou soma ponderada configuravel, e resultados com scores e ranks.
- Implementar `PGVectorHybridStore` e `PineconeHybridVectorStore`; no Pinecone, usar `sparse_values` nativos e exigir indice de dimensao 1024 com metrica `dotproduct`.
- Cachear embeddings de consulta em Redis com chave SHA-256, TTL e fail-open.
- Reindexar os 21 documentos por `scripts/reindex_kb.py`, de forma idempotente, usando o modelo local e sem embedder falso.
- Nao aplicar o reranker nesta etapa; ele continua disponivel para a etapa de top-N 4.

## Alternativas consideradas
- **Adicionar colunas na tabela antiga e tornar `embedding` nullable:** reduz duplicacao, mas obriga a alterar o caminho antigo e consultas existentes; descartado para manter o antigo intacto.
- **Guardar o vetor esparso como JSONB/arrays:** simples, mas nao permite um top-K esparso eficiente; a tabela de termos usa o indice por `token_id`.
- **Fazer a fusao dentro do PGVector:** esconderia a regra de negocio no banco e dificultaria testar RRF e pesos; a fusao fica na aplicacao.
- **Usar o Pinecone como fonte de cache:** aumenta custo e latencia; o cache fica no Redis, que ja e dependencia da aplicacao.
- **Reindexar com embedder falso para "funcionar" sem modelos:** produziria dados enganosos; o script falha claramente sem o BGE-M3.

## Consequencias
- Ha duplicacao controlada de chunks entre o caminho antigo e o novo. A flag decide qual caminho e usado; a tabela antiga pode ser removida em uma fase futura.
- A reindexacao real exige os modelos em `models/retrieval` e espaco em disco. Sem eles, a validacao real fica NAO VALIDADA.
- O indice Pinecone precisa ser criado com dimensao 1024 e metrica `dotproduct`; a alteracao de um indice existente e uma operacao externa.
- A busca esparsa em SQL e o HNSW sao validados por teste Docker; a qualidade da fusao depende de calibracao com consultas reais.
- O caminho antigo continua funcionando quando `HYBRID_RETRIEVAL_ENABLED=false`.
