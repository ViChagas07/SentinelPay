# ADR 0003: Artefato do Graphify nao versionado

- Status: aceito
- Data: 2026-11-14

## Contexto
O Graphify gera `graphify-out/` (graph.json, GRAPH_REPORT.md, graph.html e caches) a partir do conteudo do repositorio. A documentacao oficial trata `graphify-out/` como saida gerada, ignorada por padrao na varredura, e indica que o diretorio pode ser ignorado no git ou compartilhado apenas quando o time decidir. Versionar o artefato criaria diffs grandes e um grafo desatualizado sempre que o repositorio mudasse.

## Decisao
Ignorar `graphify-out/` no git. O grafo e regenerado localmente sob demanda com os comandos oficiais `graphify extract .` e `graphify cluster-only .`. O resultado fica em `graphify-out/` na raiz do projeto.

## Alternativas consideradas
- Versionar graph.json e relatorios: descartado por ruido de diff, conflitos e risco de o grafo ficar defasado.
- Nao usar Graphify: descartado porque o grafo reduz o custo de orientacao de sessoes futuras.

## Consequencias
Cada clone precisa regenerar o grafo quando for usa-lo. O artefato nao acompanha o repositorio nem serve como fonte de verdade. Se o time passar a compartilhar o grafo entre ambientes, a decisao deve ser revista em novo ADR.
