# ADR 0010: Pagamentos, notificações e inteligência com dados reais

- Status: aceito
- Data: 2026-11-16
- Fase: F09

## Contexto

O backend oferece payables, notificações e preferências, mas não oferece um cadastro
manual de recibo, exclusão de vencimento, edição de descrição ou valor, SSE, canal por
notificação, verificação de contato nem qualquer endpoint de inteligência antifraude.
O GET de preferências mascara o destino de SMS e WhatsApp, enquanto o PUT substitui os
três canais e exige o destino completo de todo canal telefônico habilitado.

## Decisão

### Pagamentos ancorados em payables

- A lista, o resumo e a linha do tempo usam `GET /api/v1/payables`, com amostra por
  cursor de até 500 itens e filtro de status no servidor.
- A situação exibida é uma camada de apresentação sobre `status` e `due_date`: a vencer,
  vence hoje, vencido, pago, dispensado e a confirmar. O status bruto não é reescrito.
- A descrição do payable é exibida como "Descrição / emissor" e a interface explica que
  o emissor não é um campo separado no contrato.
- Confirmar, pagar e ajustar vencimento usam as rotas reais. Excluir fica desabilitado
  porque não existe DELETE.
- O cadastro de recibo é um upload real para `POST /api/v1/analyses` com `kind=receipt`.
  Emissor, valor e vencimento não são enviados: o contrato não aceita esses campos e o
  pipeline os extrai do documento. O arquivo é obrigatório, apesar do pedido de anexo
  opcional, porque a API não aceita cadastro sem documento.
- A antecedência e o horário do lembrete usam as preferências globais de payables. Não
  existe lembrete por recibo. Os canais de e-mail, SMS e WhatsApp continuam nas
  preferências de notificação.

### Notificações com cursor, polling e preferências otimistas

- A lista usa `useInfiniteQuery` com cursor, filtro de tipo e de não lidas no servidor.
  Não há SSE, então a página faz polling a cada 20 segundos e compartilha a consulta de
  `unread-count` com o badge da sidebar.
- O filtro de canal fica desabilitado e explicado porque a resposta não tem canal.
- Cada item deriva o destino do payload: análise vai para o dossiê, payable vai para
  `/pagamentos?vencimento=[id]`; sem destino, o item não é link.
- As ações de leitura usam atualização otimista e reversão, atualizando lista e contador.
- As preferências de canal usam PUT completo com atualização otimista e reversão. Todo
  canal telefônico habilitado exige redigitar o número E.164, porque o GET só devolve o
  destino mascarado e o PUT não faz merge. A interface explica essa limitação em vez de
  enviar o valor mascarado ou desabilitar canais sem aviso.
- O estado de contato exibido é `consented_at`. A API não tem verificação de contato.

### Inteligência sem dados

- Sem endpoint de catálogo, casos, modelos ou métricas, a página mostra apenas um estado
  "Em desenvolvimento" com título serif, frase honesta e botão para o painel.
- Nenhum número, gráfico ou caso histórico é inventado. As lacunas ficam em
  `BACKEND_GAPS.md`.

## Consequências

- A central de pagamentos é útil com os dados reais, mas não substitui um cadastro manual
  de contas enquanto o backend não aceitar metadados e anexo opcional.
- A central de notificações cobre leitura, filtros suportados e preferências, com a
  limitação explícita de canal e verificação.
- A página de inteligência fica pronta para receber dados sem antecipar métricas.
