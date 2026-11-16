# SentinelPay Frontend

Interface do SentinelPay, SaaS antifraude para boletos, contracheques e recibos brasileiros.

## Stack

- Next.js App Router com TypeScript strict e Turbopack
- Tailwind CSS com tokens em CSS variables
- shadcn/ui customizado em `components/ui`
- TanStack Query para estado de servidor
- Zod para validar toda resposta de API
- Vitest, Testing Library e Playwright

## Comandos

Requisitos: Node.js 22 ou superior, npm 11 ou superior e Docker para os testes que usam o backend real.

```bash
npm install
npx playwright install chromium
npm run dev
npm run check
npm run test:e2e
npm run test:a11y
npm run test:a11y:report
npm run analyze
npm run lighthouse
npm run audit
```

`npm run check` executa lint, typecheck, testes unitários, portões de conteúdo e build de produção.

- `npm run check:content` valida i18n, dados fictícios, travessão longo e padrões inseguros.
- `npm run test:a11y` roda a matriz axe, a verificação responsiva e os cabeçalhos de segurança.
- `npm run test:a11y:report` grava o relatório bruto da matriz em `docs/quality/axe-matrix.json`.
- `npm run analyze` lê o build e falha se alguma rota passar de 280 kB de JavaScript gzip.
- `npm run lighthouse` sobe o build de produção, cria uma sessão de teste no backend e mede landing e painel.
- `npm run audit` usa `npm audit --audit-level=critical`.

Os testes e2e usam a porta 3100 por padrão para evitar conflito com outros projetos locais. Use `PLAYWRIGHT_PORT` para trocar.

## Ambiente

Copie `.env.example` para `.env.local` e ajuste as variáveis.

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
API_INTERNAL_URL=http://localhost:8000
NEXT_PUBLIC_SITE_URL=http://localhost:3000
NEXT_PUBLIC_SUPPORT_URL=
NEXT_PUBLIC_PRIVACY_CONTACT_URL=
NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL=
NEXT_PUBLIC_UPLOAD_MAX_MB=25
NEXT_PUBLIC_SENTRY_DSN=
NEXT_PUBLIC_SENTRY_ENVIRONMENT=
NEXT_PUBLIC_SENTRY_RELEASE=
NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE=0
E2E_API_CONTAINER=paysentineliq-api-1
```

- `NEXT_PUBLIC_API_URL` é a origem pública da API, sem `/api/v1`.
- `API_INTERNAL_URL` é a URL que o servidor Next usa como BFF.
- `NEXT_PUBLIC_SITE_URL` alimenta metadados, Open Graph e links absolutos.
- `NEXT_PUBLIC_SUPPORT_URL` alimenta o cartão de ajuda da sidebar. Vazio oculta o cartão.
- `NEXT_PUBLIC_PRIVACY_CONTACT_URL` e `NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL` definem o canal de privacidade e LGPD.
- `NEXT_PUBLIC_UPLOAD_MAX_MB` espelha o limite do backend.
- `NEXT_PUBLIC_SENTRY_*` são opcionais. Sem DSN, nenhum SDK de observabilidade é carregado. Quando o DSN existe no build, a origem dele é liberada em `connect-src` da CSP.
- `E2E_API_CONTAINER` é o container usado para criar uma sessão real nos testes e2e e no Lighthouse.

## Sessão

O navegador nunca recebe o access token. Os Route Handlers em `app/api/v1` atuam como BFF: guardam access e refresh em cookies HttpOnly e injetam o Bearer no servidor. Detalhes em `docs/adr/0004-sessao-bff.md`.

Rotas públicas: `/`, `/login`, `/termos`, `/privacidade`. Rotas privadas: `/painel`, `/verificacao`, `/boletos`, `/folha`, `/pagamentos`, `/inteligencia`, `/notificacoes`, `/account`. Sem sessão, o middleware redireciona para `/login?next=...`. Com sessão, `/login` vai para `/painel`.

## Shell

Todas as rotas privadas usam o mesmo layout com sidebar, header, conteúdo e rodapé.

- A sidebar colapsa para modo trilho, com tooltips, e persiste a escolha no cookie `sp_sidebar`.
- No mobile, a navegação vira um Sheet com um único botão de fechar.
- O logo no topo sempre aponta para `/`.
- A paleta de comandos abre com Ctrl/Cmd+K e oferece navegação e ações.
- Atalhos: `g` e `p` para o painel, `g` e `v` para a verificação, `n` para nova verificação e `?` para a lista completa.
- O cartão de ajuda usa `NEXT_PUBLIC_SUPPORT_URL`.
- Organização, avatar do Google e busca de documentos dependem de dados que a API ainda não oferece. O shell não inventa esses dados e as lacunas estão em `docs/BACKEND_GAPS.md`.

A arquitetura do shell está em `docs/adr/0005-shell.md`.

## Contrato e tipos

O contrato observado está em `docs/API_CONTRACT.md`. As lacunas de backend estão em `docs/BACKEND_GAPS.md`.

Para gerar tipos a partir do OpenAPI local, com a API em execução:

```bash
npm run api:types
```

O comando grava `lib/api/generated/openapi.d.ts`. Os schemas Zod em `lib/api/schemas` continuam sendo a validação de runtime.

## Design system

O catálogo interno fica em `/dev/design` e só responde em desenvolvimento. `middleware.ts` bloqueia a rota com 404 em produção.

A rota mostra os componentes nos temas claro e escuro e nos idiomas pt, es e en. Os testes e2e incluem axe, validação do layout mobile e geração de screenshots em `docs/design/`.

## Estrutura

A árvore de pastas e as fronteiras entre `app/`, `components/`, `features/`, `lib/api/`, `lib/i18n/`, `lib/risk/`, `lib/shell/` e `styles/` estão em `docs/adr/0001-estrutura.md`.

## Segurança

- CSP, `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors`, `X-Frame-Options` e `Permissions-Policy` são aplicados em `next.config.ts` para todas as rotas. HSTS entra fora de desenvolvimento.
- Cookies de sessão são HttpOnly e SameSite=Lax, com Secure em HTTPS ou quando `x-forwarded-proto` indica HTTPS.
- Nenhum token fica acessível ao JavaScript. O BFF injeta o Bearer no servidor.
- 401 leva ao login, 403 mostra recusa de acesso e 429 respeita `Retry-After` com aviso amigável traduzido.
- HTML de API nunca é injetado. Todo texto é renderizado como texto.
- `npm run check:content` bloqueia `dangerouslySetInnerHTML`, token em storage, `eval` e log esquecido.

## Deploy na Vercel

1. Importe o repositório e defina o diretório raiz como `frontend`.
2. Configure as variáveis de ambiente de produção: `NEXT_PUBLIC_API_URL`, `API_INTERNAL_URL`, `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_SUPPORT_URL`, `NEXT_PUBLIC_UPLOAD_MAX_MB` e, se houver, as `NEXT_PUBLIC_SENTRY_*`.
3. `API_INTERNAL_URL` precisa ser alcançável a partir das Functions da Vercel. Use a URL pública da API ou privacidade de rede quando disponível.
4. O build usa `npm run build`. Os cabeçalhos de borda estão em `vercel.json` e a CSP em `next.config.ts`.
5. Nunca coloque segredo, token de API ou chave privada em variáveis `NEXT_PUBLIC_*`.

## Observabilidade

A integração com Sentry é opcional. Com `NEXT_PUBLIC_SENTRY_DSN` preenchido, o SDK é carregado sob demanda e envia apenas a exceção sanitizada e tags seguras. Coleta de cookies, cabeçalhos, corpos de requisição, query string e dados de usuário fica desligada. Sem DSN, nada é enviado e nenhum chunk de observabilidade é carregado.

## Qualidade

O relatório da revisão final, com axe, Lighthouse, bundle, responsividade e auditoria, está em `docs/QUALITY.md`. A especificação da fase está em `docs/specs/F11.md` e a decisão em `docs/adr/0012-qualidade-seguranca-desempenho.md`.

## Dados

A interface não usa dado mockado. Estados vazios, de carregamento e de erro são obrigatórios. Dados sintéticos existem apenas em testes automatizados.
