# ADR 0009: Listas de boletos e folha com estado na URL e amostra real

- Status: aceito
- Data: 2026-11-16
- Fase: F08

## Contexto

`GET /api/v1/analyses` aceita apenas `limit` e `cursor`. O item devolve `id`, `status`,
`kind`, `score`, `band`, `error_code`, `created_at` e `updated_at`. O backend não oferece
filtro por tipo, status, classe, período ou texto, não oferece total por classe e não
devolve os campos extraídos do documento (número, beneficiário, CNPJ, valor, vencimento,
competência e líquido). Exportação CSV e exclusão de análise também não existem.

O pedido de produto exige contagens reais, filtros, ordenação e paginação. Alterar o
backend está fora do escopo da fase.

## Decisão

### Amostra real por cursor

- O front-end segue o cursor do contrato com `limit=50` até 10 páginas (500 análises mais
  recentes). Essa amostra é a fonte única de contagens, filtros, ordenação e páginas.
- Quando o cursor ainda existe no limite, `truncated=true`, a interface mostra a nota de
  amostra parcial e as contagens recebem "+". Nenhum total é inventado.
- A consulta usa `queryKeys.analyses.library`, então a invalidação existente de
  `["analyses"]` após um envio também atualiza as listas.

### Estado na URL

- Filtros, ordem, direção e página vivem em query params estáveis: `band`, `status`,
  `period`, `q`, `sort`, `dir` e `page`.
- Valores padrão são omitidos da URL. Qualquer visão pode ser copiada e recarregada.
- Mudança de filtro volta para a página 1; mudança de página preserva os demais params.
- Página fora do intervalo é ajustada para a última página válida.

### Polling com backoff

- Enquanto houver item `queued` ou `processing` na amostra, a consulta refaz a leitura e
  reutiliza os intervalos da F07 (`pollIntervalFor`): 2,5 s no primeiro minuto, 5 s até
  3 minutos, 10 s até 8 minutos e 20 s depois.
- O relógio de backoff começa no primeiro job ativo e é zerado quando não há mais jobs
  ativos. A consulta para sozinha.
- A linha em análise mostra um indicador discreto e um aviso `aria-live` informa que a
  lista está sendo atualizada.

### Campos indisponíveis

- A tabela tem as colunas pedidas, mas os campos ausentes mostram "Indisponível" com uma
  explicação curta. Não há valor, CNPJ, nome ou vencimento fictício.
- Faixa de valor, emissor/CNPJ e ordenação por valor aparecem desabilitados com o motivo.
- A busca cobre o identificador da análise, único campo textual do contrato.
- Exportação CSV e exclusão não são exibidas porque as rotas não existem. A lacuna fica
  registrada em `docs/BACKEND_GAPS.md`.

### Acessibilidade e teclado

- As abas usam o componente Tabs da F02 e cada painel contém a tabela ativa.
- O link principal da linha aceita setas para cima e para baixo para mover o foco entre
  linhas visíveis; Enter abre o dossiê pelo comportamento nativo do link.
- No mobile, a RiskRuler média fica visível na lista empilhada, sem rolagem horizontal.

## Consequências

- As contagens são exatas para a amostra carregada. Contas com mais de 500 análises veem
  a nota de amostra parcial e contagens com "+".
- A paginação da visão é local sobre a amostra; o transporte continua paginado por cursor
  no servidor. Quando o backend expuser filtros, totais e ordenação, a amostra pode ser
  substituída por uma chamada por página sem mudar a URL nem a composição da tela.
- O custo de rede cresce com o tamanho da conta, limitado a 10 requisições por leitura e
  reduzido pelo cache do TanStack Query e pelo polling com backoff.
