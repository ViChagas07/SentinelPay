# ADR 0007: Dados e estados do painel

- Status: aceito
- Data: 2026-11-16
- Fase: F06

## Contexto

O contrato atual não tem endpoint de totais, médias, séries ou distribuição. O painel
precisa mostrar risco médio, variação, conformidade, distribuição e contagens, além de
listas de análises e vencimentos. O produto proíbe dado inventado e exige estado honesto
quando falta informação.

## Decisão

### Resumos calculados com escopo explícito

- O painel pagina `GET /api/v1/analyses` até 500 itens e calcula os resumos sobre os itens
  retornados no período. A lista é ordenada por criação, então é possível parar quando o
  item mais antigo passa da janela.
- Quando a paginação atinge o limite antes do fim da janela, a interface marca "Amostra
  parcial" e os contadores recebem sufixo "+". A média e a conformidade são apresentadas
  como média e proporção da amostra do período.
- A frase de contexto e a variação são calculadas com esse mesmo conjunto. Não há
  arredondamento para uma métrica que não existe na API.
- O gap de um resumo oficial fica registrado em `docs/BACKEND_GAPS.md` com a rota
  proposta.

### Duas escalas separadas

- O "Risco médio" é um score de 0 a 100 e usa RiskRuler.
- "Documentos em conformidade" é uma proporção de análises de risco baixo sobre análises
  concluídas. Usa `role="progressbar"`, barra e rótulo próprios. Nunca é posicionada
  sobre a régua de risco.
- A faixa do risco médio é derivada com a mesma função de faixas usada no restante do
  produto, com a nota "faixa calculada sobre a média".

### Listas e vencimentos

- A tabela de análises recentes usa a primeira página da lista. Campos que a API não
  expõe aparecem como "Indisponível", com nota e gap. O ID da análise é o elo real para
  `/verificacao/[id]`.
- Os vencimentos usam a lista de payables com status ativo. A ordem é reaplicada no
  cliente por uma função pura testada, para não depender da ordenação implícita.
- A contagem de comprovantes pendentes usa a primeira página de ativos. Se houver próximo
  cursor e a contagem for maior que zero, o valor recebe "+". Se for zero, aparece
  "Indisponível" em vez de um zero que pode estar errado.

### Tempo e idioma

- A data da saudação e os rótulos de vencimento usam o fuso do perfil, validado com
  fallback para UTC.
- As datas relativas usam `Intl.RelativeTimeFormat` no idioma da interface. A data
  relativa de uma análise não depende do fuso, mas o rótulo de vencimento depende do dia
  local.
- O período selecionado no gráfico (7, 30 ou 90 dias) também governa a média, a variação,
  a conformidade e as métricas do período para manter a leitura coerente.

### Atualização

- As consultas do painel usam `refetchOnWindowFocus: true`. O shell mantém a atualização
  de alertas e a troca de título e favicon.
- O carregamento inicial mostra shimmer. Erros de seção têm botão de tentar de novo.

## Consequências

- Os números do painel são reais, mas podem ser uma amostra quando a conta tem mais de
  500 análises no período. A interface deixa isso visível.
- A tela depende de várias requisições de lista. O limite e o cache de 30 segundos
  controlam o custo.
- Quando o backend criar os endpoints de dashboard, o front-end troca a fonte dos resumos
  sem mudar a composição visual.
- O detalhe da análise ainda não existe no front-end. O link aponta para uma rota
  provisória honesta até a fase correspondente.
