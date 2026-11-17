# Reparo de texto da knowledge base (ETAPA E)

## Diagnostico
A inspecao por codepoints dos 21 PDFs de `knowledge/` mostrou que a camada de texto extraida pelo PyMuPDF ja estava em Unicode correto:

- 0 caracteres de substituicao (`U+FFFD`).
- 0 sequencias duplamente codificadas do tipo `Ã£`, `Ã©`, `Ã­`, `â€`.
- 0 documentos com decomposicao Unicode fora de NFC.
- 78 travessoes longos (`U+2014`) e 10 travessoes medios (`U+2013`).

O aspecto de mojibake observado nos artefatos da ETAPA D vinha da gravacao/leitura dos arquivos de resultado em encoding inconsistente, nao de corrupcao no texto dos PDFs. A correcao foi feita em duas frentes:

- `repair_text` em `infrastructure/rag/text_cleanup.py`: `ftfy`, NFC, normalizacao de quebras de linha, espaco nao separavel, travessao longo e travessao medio.
- Escrita e leitura dos artefatos de eval sempre em UTF-8, com limpeza de exibicao dos snippets.

## Antes e depois

| Metrica | Antes | Depois |
| --- | ---: | ---: |
| `U+FFFD` | 0 | 0 |
| Sequencias duplamente codificadas | 0 | 0 |
| Travessao longo (`U+2014`) | 78 | 0 |
| Travessao medio (`U+2013`) | 10 | 0 |
| Documentos fora de NFC | 0 | 0 |
| Chunks hibridos | 56 | 53 |

A mudanca de 56 para 53 chunks ocorre porque a substituicao de travessoes altera o conteudo e os limites do chunking, nao porque documentos foram removidos.

### Amostras

Antes:

- `Manual FEBRABAN [U+2014] Boleto Bancário`
- `FAQ Antifraude [U+2014] Perguntas e Respostas`

Depois:

- `Manual FEBRABAN, Boleto Bancário`
- `FAQ Antifraude, Perguntas e Respostas`

## Reindexacao

Comando:

```powershell
make reindex-kb
```

Resultados:

- Primeira execucao: `documents=21`, `chunks=53`, `skipped=2`, `failures=0`, `22,20 s`.
- Segunda execucao: `documents=21`, `chunks=0`, `skipped=21`, `failures=0`, `20,64 s`.

Os 2 documentos pulados na primeira execucao nao tinham travessao nem outra mudanca de normalizacao. A segunda execucao confirma a idempotencia.

## Escopo
- A reindexacao atualiza as tabelas hibridas `knowledge_hybrid_chunks` e `knowledge_hybrid_chunk_sparse_terms`.
- A tabela legada `knowledge_chunks` de 8 dimensoes nao foi reindexada nesta etapa e permanece intacta.
- O conteudo dos PDFs nao foi alterado; apenas a extracao, a normalizacao e os artefatos de eval.
