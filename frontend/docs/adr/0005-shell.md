# ADR 0005: Shell autenticado

- Status: aceito
- Data: 2026-11-16
- Fase: F04

## Contexto

A F03 entregou sessão e uma casca mínima. A F04 precisa de navegação persistente, hierarquia clara, atalhos e indicadores reais sem tocar nos tokens, nos componentes da F02, no middleware ou na sessão.

## Decisão

### Estrutura

- O route group `(app)` tem um layout de servidor que lê o cookie de modo da sidebar e monta o `AppShell` cliente.
- O shell tem sidebar fixa no desktop, header fixo no topo do conteúdo, área principal com `PageTransition` e rodapé discreto.
- Todas as rotas privadas usam o mesmo layout. Rotas de detalhe futuras herdam breadcrumbs.

### Sidebar

- Base `--petrol-sidebar`, item ativo `--petrol-active`, texto `--on-petrol`.
- O indicador ativo usa `layoutId` do motion. Com movimento reduzido, o indicador é estático.
- O modo trilho é persistido no cookie `sp_sidebar` com valores `expanded` e `rail`. O layout de servidor lê o cookie para evitar divergência de hidratação.
- No modo trilho, os itens mostram apenas ícones, com Tooltip e texto acessível.
- O logo no topo sempre aponta para `/`, nunca para o painel.
- No desktop existe apenas o controle de recolher e expandir. Não existe botão de fechar.
- No mobile a navegação vira `Sheet` do F02, que já traz um único botão de fechar. Nenhum botão extra é adicionado.
- A ordem dos itens é fixa: Painel Principal, Central de Pagamentos, Central de Verificação, Inteligência Antifraude, Folha de Pagamento, Boleto Bancário, Notificações. Minha conta fica no menu do usuário.

### Organização e usuário

- O seletor de organização aceita zero, uma ou várias organizações. Sem organização, não renderiza. Com uma, mostra nome e plano sem dropdown. Com várias, usa DropdownMenu.
- A API atual não devolve organização, avatar nem plano. O componente está pronto para o contrato, mas o shell não inventa dados. As lacunas estão em `BACKEND_GAPS.md`.
- O avatar usa iniciais do nome real ou do e-mail até a API devolver `avatar_url`.
- O cartão de ajuda só aparece quando `NEXT_PUBLIC_SUPPORT_URL` é uma URL http(s) válida.

### Header

- Título derivado do mapa de rotas, breadcrumbs em `/account` e `/verificacao/nova`.
- Busca abre a paleta de comandos.
- Idioma, tema e menu do usuário. No mobile, idioma e tema ficam dentro do menu do usuário para não estourar a largura.

### Busca e comandos

- Ctrl/Cmd+K abre a paleta.
- A paleta oferece navegação e ações. O endpoint `/api/v1/search` não existe hoje, então a paleta mostra uma linha explícita de indisponibilidade e não executa consulta.
- Quando o endpoint existir, a integração deve usar debounce e `AbortController`, com schema Zod próprio. Nada disso é inventado agora.

### Atalhos

- `g` seguido de `p` vai ao painel; `g` seguido de `v` vai à verificação; `n` abre a nova verificação; `?` abre a lista.
- O listener ignora campos editáveis, elementos com `data-shortcuts="ignore"`, repetição e composição de IME.
- Quando a paleta, o sheet ou o diálogo de atalhos está aberto, os atalhos globais ficam desativados.

### Alertas

- O título da aba e o favicon usam a contagem de notificações `high_risk_detected` não lidas. O front-end pagina o endpoint de notificações existente, com limite de segurança de 500 itens e indicação de truncamento.
- Quando a contagem volta a zero, o título e o favicon normais retornam.
- O badge da sidebar usa o total real de não lidas de `GET /api/v1/notifications/unread-count`.

### Responsividade

- O shell usa `min-w-0` e evita larguras mínimas rígidas.
- Em 360px, a sidebar é Sheet, o header mostra menu, título truncado, busca icônica e avatar.
- Testes e2e verificam ausência de rolagem horizontal em rotas representativas.

## Consequências

- A organização e o avatar só aparecerão quando o backend expuser os dados. Até lá, o shell não simula nada.
- O indicador de risco alto faz paginação de notificações. Se o volume crescer, o backend deve oferecer contagem agregada por tipo.
- O modo trilho é uma preferência local, não sincronizada entre dispositivos.
- A paleta deve ser estendida quando `/api/v1/search` existir, mantendo o estado de indisponibilidade atual como fallback.
