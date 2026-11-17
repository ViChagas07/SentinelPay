# ADR 0025: Bi-encoder BGE-M3 e cross-encoder v2-m3 em CPU

- Status: aceito
- Data: 2026-11-17
- Relacionado: SPEC 0022, ADR 0022, ADR 0023, ADR 0024, `eval/RESULTS.md`

## Contexto
A P17.1 precisava de retrieval em dois estagios para a base de 21 documentos regulatorios e antifraude, com consultas em portugues, espanhol e ingles. O ambiente nao tem GPU e a regra do projeto exige CPU, sem CUDA, ROCm ou DirectML. A avaliacao da ETAPA D comparou denso, hibrido e hibrido com reranker usando 30 perguntas, Recall@5, MRR, latencia p50/p95 e modelos int8 em ONNX Runtime.

## Decisao
- Estagio 1: `BAAI/bge-m3` como bi-encoder, gerando embedding denso de 1024 dimensoes e pesos esparsos. A busca hibrida combina os dois por RRF, com top-K 25.
- Estagio 2: `BAAI/bge-reranker-v2-m3` como cross-encoder, reranqueando os 25 candidatos e entregando top-N 4 ao Qwen.
- Execucao local em CPU, com ONNX Runtime int8 como caminho padrao e fallback PyTorch CPU.
- Timeout do reranker calibrado em 30 s, com fallback para a ordem do estagio 1.
- Manter o caminho denso e o caminho hibrido disponiveis por flag para comparacao e degradacao.

## Justificativa
- **BGE-M3 no estagio 1:** um unico modelo cobre dense, sparse e multi-vector, e o dense de 1024 dimensoes e multilíngue. Isso evita manter um modelo lexical separado e atende pt, es e en no mesmo indice. A avaliacao local mostrou denso com Recall@5 0,9333 e MRR 0,8917; o hibrido RRF ficou em 0,8667 e 0,8011 neste corpus pequeno, o que reforca a necessidade de reranking e de calibracao futura.
- **BGE reranker v2-m3 no estagio 2:** o cross-encoder avalia o par consulta/documento em conjunto, capturando relacoes que o bi-encoder comprime em um unico vetor. O v2-m3 e multilíngue e compartilha a familia do BGE-M3. Na avaliacao, o rerank elevou Recall@5 para 0,9667 e MRR para 0,9583, corrigindo casos em que o estagio 1 colocava um documento generico ou vizinho no topo.
- **CPU e ONNX Runtime int8:** nao ha GPU no ambiente de execucao, e CUDA, ROCm e DirectML sao proibidos. O int8 reduz memoria e custo por consulta em CPU. O fallback PyTorch CPU cobre ambientes sem ONNX ou com problema de conversao. A avaliacao usou conversoes int8 da comunidade (`onnx-community/bge-m3-ONNX` e `onnx-community/bge-reranker-v2-m3-ONNX`), derivadas dos pesos BAAI, com o `sparse_linear.pt` oficial. A conversao oficial pelo `warmup_models.py` continua sendo o caminho de producao.
- **Top-K 25 e top-N 4:** 25 candidatos preservam recall do estagio 1 sem rerankar a base inteira. O top-N 4 limita o custo do cross-encoder e entrega ao Qwen apenas os trechos mais relevantes.
- **Timeout 30 s:** na avaliacao int8 em CPU, o rerank teve p50 de 12,08 s e p95 de 13,44 s. Um timeout de 5 s fazia todas as consultas cairem no fallback, anulando o estagio 2. O valor de 30 s preserva o rerank na maior parte das consultas e ainda limita a espera.

## Resultados da avaliacao
Dataset: 30 perguntas, 10 por idioma, cobrindo FEBRABAN, INSS, CLT e padroes de fraude. Top-K 25, K da metrica 5, ONNX Runtime int8 em CPU, sem cache.

| Modo | Recall@5 | MRR | p50 | p95 |
| --- | ---: | ---: | ---: | ---: |
| Denso BGE-M3 | 0,9333 | 0,8917 | 80,19 ms | 87,17 ms |
| Hibrido RRF | 0,8667 | 0,8011 | 84,21 ms | 91,96 ms |
| Hibrido + rerank | 0,9667 | 0,9583 | 12.076,74 ms | 13.440,36 ms |

Detalhes, consultas e trechos em `eval/RESULTS.md`.

### Segunda rodada (ETAPA E)
Depois do reparo de extracao e da reindexacao, o eval passou a comparar seis modos. O conjunto e o mesmo de 30 perguntas, top-K 25, top-N 5 para a metrica e CPU int8:

| Modo | Recall@5 | MRR | p50 | p95 |
| --- | ---: | ---: | ---: | ---: |
| Denso BGE-M3 | 0,9333 | 0,8917 | 90,11 ms | 96,16 ms |
| Denso + rerank | 0,9667 | 0,9611 | 14.244,38 ms | 15.180,27 ms |
| Hibrido RRF | 0,8667 | 0,8011 | 84,40 ms | 457,67 ms |
| Hibrido ponderado 0,7/0,3 | 0,8667 | 0,8344 | 84,54 ms | 92,34 ms |
| Hibrido RRF + rerank | 0,9667 | 0,9417 | 12.814,01 ms | 14.333,89 ms |
| Hibrido ponderado + rerank | 0,9667 | 0,9583 | 13.015,21 ms | 13.580,81 ms |

Achados:
- O hibrido RRF continuou abaixo do denso no top-5, confirmando o resultado da primeira rodada. A fusao ponderada 0,7/0,3 melhorou o MRR do estagio 1 de 0,8011 para 0,8344, sem mudar o Recall@5.
- Rerankar o denso deu o melhor MRR (0,9611), mas com o maior p50 (14,2 s). O hibrido ponderado + rerank ficou proximo (0,9583) com p50 menor (13,0 s).
- O ganho de MRR do rerank sobre o estagio 1 foi grande: +0,127 no ponderado e +0,141 no RRF. O rerank continua sendo o estagio que define a precisao do topo.
- A extracao dos PDFs nao tinha mojibake real na camada de texto; o defeito visivel era encoding dos artefatos. A normalizeacao removeu 78 travessoes longos e 10 medios, e a reindexacao passou de 56 para 53 chunks por causa dos limites de chunk.

### Benchmark de K, max_length e precisao (ETAPA E)
O benchmark usou 3 consultas, candidatos top-25 do RRF, e mediu apenas o rerank em CPU. A tabela completa, com 18 configuracoes, esta em `eval/RESULTS.md`.

- Recall de candidatos do estagio 1: K=10 em 0,9667, K=15 em 0,9667 e K=25 em 1,0000. Reduzir K perde documentos esperados, entao K=25 foi mantido.
- Cobertura de tokens dos pares: max_length 256 cobre 30,93%, 384 cobre 97,60% e 512 cobre 100%.
- Latencia int8 com K=25: 256 em 7.438,86 ms, 384 em 13.220,49 ms e 512 em 12.570,10 ms. A variacao de 384/512 esta dentro do ruido de uma medicao curta, mas 512 garante cobertura total.
- Latencia fp32 com K=25: 256 em 13.340,81 ms, 384 em 20.591,50 ms e 512 em 21.066,99 ms. O int8 foi cerca de 1,7 a 2 vezes mais rapido.
- Recomendacao final: **int8, K=25, max_length=512**. O int8 e obrigatorio pela regra de CPU e mais rapido; K=25 preserva o recall de candidatos; 512 cobre 100% dos pares e teve p50 menor do que 384 nesta execucao. `RERANK_MAX_LENGTH` permanece 512; `RETRIEVAL_TOP_K` permanece 25; `RERANK_TOP_N` de producao permanece 4.

O servico `api` passou a montar `./models` como somente leitura e o `/health` do container confirmou `loaded=true` para embedder, sparse embedder e reranker.

## Alternativas consideradas
- **Somente denso:** tem boa recall neste corpus, mas nao aproveita termos raros, codigos e nomes de campos que o sinal esparso captura, e nao melhora a precisao do topo.
- **Somente BM25 ou esparso:** e barato, mas fraco para parafrases e consultas multilíngues.
- **Embeddings hospedados:** reduz operacao local, mas adiciona custo, latencia, dependencia de rede e envio de consultas para terceiros.
- **Reranker hospedado:** fica disponivel como `RemoteReranker`, mas nao e o padrao por privacidade, custo e disponibilidade.
- **GPU:** proibida pelas regras do projeto.
- **Modelo cross-encoder apenas em ingles:** nao atende pt e es.

## Consequencias
- O rerank melhora a precisao do topo, mas custa cerca de 12 s por consulta em CPU int8 neste ambiente. O uso em producao exige monitorar p95 e talvez reduzir top-K, aumentar batching ou usar o reranker remoto.
- O hibrido RRF nao superou o denso neste corpus pequeno. A decisao mantem as duas rotas e a flag para permitir calibracao com uma base maior, pesos diferentes ou outro modo de fusao.
- Os modelos ocupam espaco local e ficam fora do git. O `api` ainda nao monta `models/`, pendencia de infraestrutura.
- A avaliacao tem 30 perguntas e 21 documentos; os numeros sao indicativos e nao substituem uma avaliacao com analistas e consultas reais.
- A conversao int8 oficial, o fallback PyTorch, o reranker remoto real e o Pinecone real continuam NAO VALIDADOS.
