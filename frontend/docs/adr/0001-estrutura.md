# ADR 0001: Estrutura do front-end

- Status: aceito
- Data: 2026-11-15
- Fase: F00 (descoberta)

## Contexto

O front-end do SentinelPay será construído do zero em `frontend/`, com Next.js App Router, TypeScript strict, Tailwind, shadcn/ui customizado, TanStack Query para estado de servidor, Zod na fronteira da API, motion para animação e lucide-react para ícones. A interface tem três idiomas de rótulos (`pt-BR` padrão, `es` e `en`), precisa atender WCAG AA e não pode exibir dado mockado.

O backend expõe uma API REST versionada em `/api/v1`, com autenticação por Bearer token, refresh em cookie HttpOnly e erros problem+json. O contrato observado está em `frontend/docs/API_CONTRACT.md`. As lacunas estão em `frontend/docs/BACKEND_GAPS.md`.

Esta ADR define a estrutura de pastas e as fronteiras entre camadas. Decisões específicas de autenticação, i18n, gráficos e animação terão ADRs próprias quando forem implementadas.

## Decisão

### 1. Árvore de pastas

```text
frontend/
  app/
    layout.tsx
    page.tsx
    providers.tsx
    not-found.tsx
    error.tsx
    loading.tsx
    icon.svg
    login/
      page.tsx
    termos/
      page.tsx
    privacidade/
      page.tsx
    api/
      v1/
        auth/
        [...path]/
          route.ts
    (app)/
      layout.tsx
      painel/
        page.tsx
    dev/
      design/
        page.tsx
        design-showcase.tsx
    (public)/
      entrar/
        page.tsx
        erro/
          page.tsx
    (app)/
      layout.tsx
      painel/
        page.tsx
      analises/
        page.tsx
        nova/
          page.tsx
        [id]/
          page.tsx
      boletos/
        page.tsx
      contracheques/
        page.tsx
      recibos/
        page.tsx
      vencimentos/
        page.tsx
      notificacoes/
        page.tsx
      inteligencia/
        page.tsx
      busca/
        page.tsx
      conta/
        page.tsx
      configuracoes/
        page.tsx
      organizacao/
        page.tsx
  components/
    brand/
    ui/
      motion/
    layout/
    data-display/
    feedback/
  features/
    auth/
      components/
      hooks/
      api/
      schemas/
    analyses/
    documents/
    payables/
    notifications/
    dashboard/
    account/
    organization/
    intelligence/
    search/
    shell/
  lib/
    api/
      client.ts
      config.ts
      endpoints.ts
      errors.ts
      interceptors.ts
      locale.ts
      schemas/
    cookies.ts
    i18n/
      constants.ts
      dictionaries/
      format.ts
      provider.tsx
      translate.ts
    risk/
      presentation.ts
    shell/
      alerts.ts
      initials.ts
      organization.ts
      routes.ts
      shortcuts.ts
      sidebar-cookie.ts
    theme/
      constants.ts
      provider.tsx
      server.ts
    query/
      client.ts
      keys.ts
    utils/
  styles/
    globals.css
    tokens.css
  public/
    favicon-alert.svg
  middleware.ts
  e2e/
  public/
  tests/
  docs/
    adr/
    design/
    specs/
  PROGRESS.md
```

### 2. Fronteiras entre pastas

`app/` contém apenas roteamento, layouts, metadata, `loading.tsx`, `error.tsx` e composição de página. Página não faz `fetch` direto nem conhece detalhe de HTTP. Ela chama hooks de `features/` e monta componentes.

`components/ui/` é o design system local, derivado do shadcn/ui e customizado. Não contém regra de negócio, chamada de API nem texto fixo. `components/layout/` contém shell, navegação, cabeçalho, barra lateral e breadcrumbs. `components/data-display/` contém apresentação genérica reutilizável, como tabela, paginação por cursor, badge de status e estado vazio. `components/feedback/` contém loading, erro, toast e confirmação.

`features/<dominio>/` é a unidade de produto. Cada feature pode ter:

- `components/`: componentes específicos do domínio.
- `hooks/`: hooks de consulta e mutação com TanStack Query.
- `api/`: funções que chamam `lib/api` e validam a resposta com Zod.
- `schemas/`: schemas Zod dos recursos daquela feature.
- `lib/`: funções puras do domínio, testáveis sem React.

`lib/api/` é a única camada que conhece URL, headers, cookies, CSRF, refresh e formato problem+json. Ela não conhece layout. `lib/api/client.ts` expõe `apiFetch` com `credentials: "include"`, `Authorization` quando houver access token, `Accept-Language`, `X-CSRF-Token` em refresh/logout e `Idempotency-Key` quando aplicável.

`lib/i18n/` contém apenas rótulos e formatadores de apresentação. Nenhum texto de interface fica fora do dicionário. `lib/risk/` contém apenas o mapeamento de `band` devolvida pela API para rótulo, tom visual e ícone. Não contém cálculo de score nem de faixa.

`styles/` contém tokens, variáveis CSS e estilos globais. Tailwind é configurado por tokens semânticos, não por cores soltas em componentes.

`e2e/` contém Playwright. `tests/` contém setup do Vitest e utilitários de teste. Dados de teste ficam exclusivamente em testes, nunca em telas.

### 3. Rotas previstas

| Rota | Grupo | Depende de |
| --- | --- | --- |
| `/entrar` | público | `GET /api/v1/auth/google/login` e `POST /api/v1/auth/refresh` |
| `/entrar/erro` | público | Parâmetro de erro do callback, quando o backend oferecer o redirect seguro |
| `/painel` | autenticado | Resumo do painel, ainda sem endpoint. Hoje mostra estado de construção |
| `/analises` | autenticado | `GET /api/v1/analyses` |
| `/analises/nova` | autenticado | `POST /api/v1/analyses` |
| `/analises/[id]` | autenticado | `GET /api/v1/analyses/{id}` |
| `/boletos` | autenticado | `GET /api/v1/analyses` filtrado por `kind`, quando existir |
| `/contracheques` | autenticado | `GET /api/v1/analyses` filtrado por `kind`, quando existir |
| `/recibos` | autenticado | `GET /api/v1/analyses` filtrado por `kind`, quando existir |
| `/vencimentos` | autenticado | `GET /api/v1/payables` |
| `/notificacoes` | autenticado | `GET /api/v1/notifications` e preferências |
| `/inteligencia` | autenticado | Catálogo de regras, ainda sem endpoint |
| `/busca` | autenticado | Busca global, ainda sem endpoint |
| `/conta` | autenticado | `GET /api/v1/users/me` |
| `/configuracoes` | autenticado | Preferências de notificação e lembrete |
| `/organizacao` | autenticado | Organização, ainda sem endpoint |

Rotas que dependem de endpoint inexistente devem renderizar estado de indisponibilidade explícito, sem dado fictício. O detalhamento está em `BACKEND_GAPS.md`.

### 4. Estado de servidor e validação

- TanStack Query é a única fonte de estado de servidor. Não usar `useEffect` para buscar dado de API.
- Cada resposta passa por `schema.parse` do Zod na fronteira. Se a resposta não casar com o schema, o hook entra em estado de erro, não faz cast e não mostra dado parcial.
- Query keys ficam em `lib/query/keys.ts`, com chave por recurso e parâmetros de filtro e cursor.
- Mutações invalidam as chaves afetadas. Não duplicar dado de servidor em estado global.
- Estado local de UI (modal aberto, filtro ainda não aplicado, aba ativa) fica em `useState` ou contexto pequeno. Não usar store global para isso.
- Access token fica em memória. Refresh usa cookie HttpOnly. Não usar `localStorage` nem `sessionStorage` para token.
- No carregamento inicial, o cliente tenta `POST /api/v1/auth/refresh` com o `csrf_token` do cookie. Sucesso monta a sessão em memória; 401 significa deslogado. Não existe endpoint de sessão hoje.
- Em 401, o cliente tenta um refresh uma única vez e repete a requisição. Se o refresh falhar, limpa a sessão e leva para `/entrar`.
- Erros problem+json são normalizados em `lib/api/errors.ts` com `code`, `status`, `title`, `detail`, `requestId` e `fieldErrors` quando existirem.

### 5. Idiomas e formatação

- Idiomas de interface: `pt-BR` (padrão), `es` e `en`. Nenhum outro idioma e nenhum RTL.
- Rótulos ficam em `lib/i18n/dictionaries/` e são acessados por `useTranslation`.
- Texto vindo da API, como `justification`, é exibido como está. Ele já é produzido no locale do job.
- `message_key` de evidência e `type` de notificação são traduzidos pelo dicionário do front-end.
- Datas e números usam `Intl` com locale e timezone do usuário.
- Valores monetários de vencimento chegam como string decimal. O front-end formata a string sem passar por ponto flutuante.
- Proibido travessão longo (em dash) em qualquer texto de interface, comentário ou documento.
- Nenhum texto fixo fora do dicionário, incluindo mensagens de erro, estados vazios e rótulos de botão.

### 6. Risco

- `lib/risk/presentation.ts` recebe a `band` da API (`low`, `attention`, `high`) e devolve rótulo, tom e ícone.
- O front-end não recalcula classe nem score a partir de `score`, `base_score`, `llm_adjustment` ou faixas.
- Se uma legenda precisar citar faixas numéricas, ela é conteúdo informativo estático com fonte documentada em `frontend/docs/API_CONTRACT.md`, não uma função de classificação.
- A cor nunca é o único sinal da banda. Sempre há rótulo textual e ícone, para daltonismo e leitores de tela.

### 7. Estilo, acessibilidade e movimento

- Tailwind com tokens semânticos em `styles/tokens.css` e `styles/globals.css`.
- shadcn/ui é copiado para `components/ui/` e customizado. Não usar o tema padrão sem ajuste.
- Tema claro e escuro por `prefers-color-scheme`, com possibilidade de escolha explícita.
- Foco visível em todos os controles, navegação por teclado, landmarks, `aria-live` para estados assíncronos e contraste AA.
- motion é usado com respeito a `prefers-reduced-motion`. Animação não bloqueia ação nem esconde conteúdo.
- Gráficos serão decididos em ADR própria. Nenhuma biblioteca de gráfico é adicionada nesta fase.

### 8. Testes

- Vitest para lógica pura: formatadores, schemas Zod, clientes de API, hooks e mapeamento de risco.
- React Testing Library para componentes com comportamento.
- MSW apenas em testes, nunca em produção e nunca visível ao usuário.
- Playwright para fluxos críticos: login, upload de análise, acompanhamento até resultado, central de notificações, vencimentos e logout.
- Dados sintéticos de teste ficam em `tests/` e `e2e/fixtures/`, fora do bundle de produção.

### 9. Nomenclatura

- Arquivos e pastas em kebab-case.
- Componentes React em PascalCase.
- Hooks começam com `use`.
- Schemas Zod em camelCase com sufixo `Schema`.
- Tipos derivados de schema com `z.infer`.
- Sem `any`, sem `@ts-ignore`, sem `console.log` esquecido.
- Código e identificadores em inglês. Textos de interface em pt-BR, es ou en pelo dicionário.

## Alternativas consideradas

- Pastas por tipo (`pages/`, `services/`, `hooks/`) em vez de por feature: descartado porque espalha o mesmo domínio por vários lugares e dificulta evolução.
- `src/` dentro de `frontend/`: descartado para manter a estrutura pedida no escopo (`app/`, `components/`, `features/`, `lib/`, `styles/`).
- Zustand ou Redux para estado de servidor: descartado porque TanStack Query já cobre cache, revalidação e estados de carregamento e erro.
- Buscar dado no servidor Next.js com cookies: descartado por enquanto porque o access token é entregue no corpo do refresh e fica em memória. Se o produto exigir SSR autenticado, uma ADR futura define BFF ou proxy.
- Guardar access token em `localStorage`: descartado por XSS. O refresh fica em cookie HttpOnly e o access token em memória.
- Recalcular risco no cliente para colorir a interface: descartado porque a classe é fonte única do backend e o front-end não pode divergir da API.

## Consequências

- F01 deve criar o projeto Next.js e as pastas acima, com lint, typecheck, Vitest e build verdes.
- F02 deve escrever a ADR de autenticação e implementar o cliente de sessão com access token em memória.
- F03 deve escrever a ADR de i18n e criar os dicionários pt-BR, es e en.
- F04 deve escrever a ADR de gráficos antes de escolher biblioteca para o painel.
- Toda tela nova começa pela spec em `frontend/docs/specs/`, depois pelos schemas Zod, depois pelos hooks, depois pelos componentes.
- Enquanto um endpoint não existir, a tela mostra estado de indisponibilidade. Não criar mock, fixture visível ou resposta inventada.
