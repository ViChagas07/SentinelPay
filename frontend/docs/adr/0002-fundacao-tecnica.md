# ADR 0002: Fundação de tema, i18n e cliente de API

- Status: aceito
- Data: 2026-11-15
- Fase: F01

## Contexto

A F01 precisava entregar a base visual e técnica sem criar telas de negócio. As decisões abaixo afetam todas as fases seguintes e por isso ficam registradas.

## Decisão

### Tema

- O tema é lido de um cookie `theme` no servidor e aplicado como `data-theme` no elemento `html`.
- Valores aceitos: `system`, `light` e `dark`. O padrão é `system`.
- Com `system`, o CSS segue `prefers-color-scheme` por media query. Com `light` ou `dark`, o atributo força o tema e bloqueia a media query.
- A troca de tema grava o cookie e atualiza `data-theme` sem recarregar a página.
- O tema claro usa fundo papel e o escuro usa o fundo petróleo definido nos tokens. As cores de risco existem apenas para risco.
- Os valores obrigatórios do briefing estão em `styles/tokens.css`. Superfície elevada, texto secundário e landing do tema claro foram derivados para manter contraste AA, já que o briefing trouxe apenas fundo, superfície, borda e texto do tema claro.

### Idioma

- Idiomas de interface: `pt` (padrão), `es` e `en`. Nenhum outro idioma e nenhum RTL.
- Os dicionários são objetos tipados. A chave é o tipo `TranslationKey`, derivado do dicionário português, então chave inexistente falha no typecheck.
- O idioma é lido de um cookie `locale` no servidor e aplicado em `lang`. A troca grava o cookie, atualiza o estado e chama `router.refresh()` para os componentes de servidor.
- A tradução cai para português se uma chave faltar em tempo de execução, embora o typecheck impeça isso em tempo de compilação.
- Datas, números e moeda BRL usam `Intl`. O locale de formatação é `pt-BR`, `es` ou `en`; a moeda é sempre BRL.

### Cliente de API

- `NEXT_PUBLIC_API_URL` é a origem da API, sem `/api/v1`. O cliente acrescenta o prefixo.
- Toda chamada usa `credentials: "include"`, porque o refresh token vive em cookie HttpOnly no host da API.
- O access token fica em memória no módulo `lib/api/auth-token.ts`. Não vai para `localStorage`, `sessionStorage` nem cookie.
- O header `Authorization: Bearer` é adicionado quando há access token. O header `X-CSRF-Token` é adicionado explicitamente em refresh e logout, lendo o cookie `csrf_token`.
- O header `Accept-Language` é preenchido com o locale da interface para que a análise seja gerada no idioma correto.
- Toda resposta passa por um schema Zod. Resposta fora do schema vira `ApiError` com código `response_schema_invalid`, nunca cast silencioso.
- Erros problem+json viram `ApiError` com `status`, `code`, `title`, `detail`, `requestId`, `retryAfterSeconds`, `instance` e `evidence`.
- 401 e 403 disparam interceptores globais `onUnauthorized` e `onForbidden`. A F01 não redireciona sozinha para login; a F02 registra esse comportamento.
- O refresh automático de sessão não faz parte da F01. O hook `useRefreshSession` chama `POST /auth/refresh` e guarda o access token em memória.
- TanStack Query fica em `lib/query` e os hooks por área em `features/<area>/hooks`.

### Tipos do OpenAPI

- O script `npm run api:types` gera `lib/api/generated/openapi.d.ts` quando a API está em execução.
- Os schemas Zod continuam sendo a validação de runtime. Os tipos gerados são auxiliares, não substituem a validação.

## Consequências

- A fase de autenticação deve registrar um `onUnauthorized` que limpa o access token e leva para a tela de entrada.
- A fase de autenticação deve decidir se tenta refresh automaticamente antes de deslogar.
- A F03 pode evoluir os dicionários, mas não pode adicionar idiomas além de pt, es e en.
- Qualquer nova resposta de API precisa de schema Zod e teste do cliente ou do hook correspondente.
- A troca de tema e idioma é coberta por e2e em `e2e/foundation.spec.ts`, em porta dedicada para não colidir com outros servidores locais.
