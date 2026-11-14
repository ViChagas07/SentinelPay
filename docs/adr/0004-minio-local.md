# ADR 0004: MinIO local via imagem comunitaria fixada

- Status: aceito
- Data: 2026-11-14

## Contexto
O Compose local precisa de um servico S3 compativel para desenvolvimento. As imagens oficiais `minio/minio` foram removidas do Docker Hub em setembro de 2026 e o repositorio `quay.io/minio/minio` passou a exigir autenticacao (HTTP 401) para pulls anonimos. Nao ha imagem oficial publica disponivel para o ambiente local.

## Decisao
Usar `pgsty/minio:RELEASE.2026-08-04T00-00-00Z` (imagem comunitaria fixada; pull verificado e `/minio/health/live` retornando 200 em 2026-11-14). A imagem serve apenas ao desenvolvimento local. Producao continua usando AWS S3.

## Alternativas consideradas
- `bitnamilegacy/minio`: build de julho de 2025, anterior a correcoes de seguranca conhecidas; descartado.
- Imagem Chainguard: tier gratuito publica apenas `latest` mutavel e sem cliente `mc`; descartado para manter reprodutibilidade.
- Remover MinIO do Compose: descartado porque quebra a paridade local com S3.

## Consequencias
Ha dependencia de uma imagem comunitaria, que deve ser revista quando existir uma alternativa oficial ou mantida. A imagem roda como root no container, o que e aceitavel apenas no ambiente local. Se o Compose for usado em CI, fixar tambem pelo digest e revisar a procedencia. Nenhum dado real deve ser gravado nesse servico.
