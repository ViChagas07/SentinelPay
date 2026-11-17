# ADR 0013: SSE com fallback de polling e cancelamento no front

## Decisao
O cliente abre `EventSource` no proxy BFF (`/api/v1/analyses/{id}/events`), que repassa o cookie de sessao e o token ao backend. O snapshot inicial do SSE e aplicado no cache do TanStack Query. Se o stream falhar duas vezes, o cliente fecha o `EventSource` e ativa o polling existente de `GET /analyses/{id}`. A consulta inicial continua sendo a fonte para o resultado completo.

O cancelamento usa `useMutation` e dialogo de confirmacao. Sucesso em `queued`/`running` leva de volta a tela de envio; 409 apenas atualiza o estado e informa que a analise ja terminou.

## Motivos
- SSE atravessa o proxy atual sem mudar autenticacao.
- Snapshot no connect resolve reconexao e abertura tardia sem estado local fragil.
- Polling reaproveita o que ja existia e cobre queda de SSE, proxy ou rede.
- Nao criar WebSocket nem timer de progresso.

## Consequencias
- EventSource nao envia header customizado; o proxy BFF resolve o Bearer.
- O painel precisa combinar snapshot parcial com o detalhe em cache, sem apagar `result` ja carregado.
