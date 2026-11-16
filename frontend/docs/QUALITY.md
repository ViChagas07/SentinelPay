# Relatório de qualidade do front-end

- Fase: F11
- Data: 2026-11-16
- Ambiente: Windows 11, Node.js 22.20.0, npm 11.6.2, Next.js 16.4.6, Chrome for Testing 159.0.8154.6, Lighthouse 13.6.0
- Backend: FastAPI local em Docker (`paysentineliq-api-1`), usado apenas para sessão real, upload e Lighthouse.
- Natureza: revisão e medição. Nenhuma funcionalidade de negócio nova.

## Portões

| Comando | Resultado | Evidência |
| --- | --- | --- |
| `npm run check` | verde | lint, typecheck, 226 testes unitários, `check:content` e build de produção |
| `npm run check:content` | zero ocorrências | 3 idiomas completos, sem texto JSX fixo, sem dado fictício em produção, sem travessão longo |
| `npm run test:e2e` | verde | 158 testes na execução completa (157 verdes e 1 flake resolvido no retry); teclado das 16 rotas validado em execução dedicada, com 8 casos adicionais |
| `npm run test:a11y` | verde | matriz axe, responsivo e cabeçalhos de segurança |
| `npm run analyze` | verde | maior rota com 258,3 kB de JS gzip, abaixo do orçamento de 280 kB |
| `npm run lighthouse` | verde | landing e painel acima de 90 nas três categorias |
| `npm run audit` | sem crítica | 7 vulnerabilidades moderadas transitivas de desenvolvimento, 0 críticas e 0 altas |

## i18n

- Idiomas permitidos: `pt`, `es`, `en`. Nenhum outro locale existe em `lib/i18n`.
- 1.166 chaves em cada dicionário, com chaves e placeholders iguais.
- `scripts/check-i18n.mjs` usa a AST do TypeScript para comparar os três dicionários e varrer texto JSX fixo.
- Fora da varredura de texto fixo: `/dev/design` (catálogo interno, 404 em produção) e `app/opengraph-image.tsx` (imagem gerada, não é interface HTML).
- Textos técnicos novos, como a máscara monetária, o rótulo PDF, o atalho `n` e o cabeçalho `X-Request-ID`, foram movidos para o dicionário em vez de ficarem soltos.

## Acessibilidade

- Matriz axe em 16 rotas, 2 temas e 3 idiomas: 96 análises, zero violações.
- Rota 404, tema claro, pt: zero violações.
- `prefers-reduced-motion`: emulado nas 96 análises e verificado na landing.
- Rotas cobertas: `/`, `/login`, `/termos`, `/privacidade`, `/suporte`, `/servico-indisponivel`, `/painel`, `/verificacao`, `/verificacao/nova`, `/verificacao/[id]`, `/boletos`, `/folha`, `/pagamentos`, `/notificacoes`, `/account`, `/inteligencia`.
- Passagem somente por teclado nas 16 rotas: primeiro Tab no skip link, pelo menos 5 elementos interativos por rota, foco visível em todos e nenhum foco perdido.
- Corrigido: ordem de títulos em `/servico-indisponivel` (h1 para h2 antes do card).
- Corrigido: nome acessível das verificações recentes, que agora inclui o texto visível e o rótulo "Abrir análise".
- Relatório bruto: `docs/quality/axe-matrix.json` (gerado por `npm run test:a11y:report`). O Playwright registrou 18 casos, 0 inesperados, 0 flaky e 0 pulados.

## Responsivo

- Rotas verificadas em 360, 768, 1280 e 1920 px: 16 rotas, 64 combinações.
- `document.documentElement.scrollWidth` nunca excede `clientWidth` em mais de 1 px.
- A régua de risco do painel e do dossiê foi medida nas quatro larguras: três faixas visíveis, soma igual à trilha com tolerância de 3 px, sem rolagem interna e sem sair da viewport.
- Correção de desempenho estrutural: a transição de página não anima mais opacidade, o que também removeu atraso de pintura do conteúdo no mobile.

## Lighthouse

Medição de laboratório contra build de produção, servidor em `127.0.0.1:3210`, sessão real de teste e dados reais do backend.

| Página | Desempenho | Acessibilidade | Boas práticas | Relatório |
| --- | --- | --- | --- | --- |
| Landing `/` | 99 | 100 | 96 | `docs/quality/lighthouse-landing.json` |
| Painel `/painel` | 93 | 100 | 96 | `docs/quality/lighthouse-painel.json` |

Métricas principais: landing com FCP e LCP de 1,06 s, TBT de 138 ms e CLS 0; painel com FCP e LCP de 0,76 s, TBT de 324 ms e CLS 0.

Correções que sustentam o resultado do painel:

- O usuário inicial do shell é resolvido no servidor, com timeout de 2,5 s e fallback para o cliente.
- O título de saudação passa a ser renderizado no HTML inicial e vira o LCP.
- A transição de página não usa opacidade inicial.
- Visualizador de documento e gráficos são carregados sob demanda.

## Bundle

Build de produção, JavaScript de entrada por rota em gzip:

| Grupo | Faixa | Maior rota |
| --- | --- | --- |
| Rotas públicas | 157,0 kB a 212,6 kB | `/` |
| Rotas privadas | 232,1 kB a 258,3 kB | `/account` |

- Orçamento definido: 280 kB de JS gzip por rota.
- Maiores chunks: runtime compartilhado de 70,0 kB, 54,7 kB e 50,2 kB; o chunk do Sentry tem 135,8 kB e só é baixado quando existe DSN configurado.
- O visualizador de PDF e os gráficos saem do carregamento inicial por `next/dynamic`.
- Não há imagem remota. As únicas imagens são o favicon local e a imagem Open Graph gerada no servidor; prévias de documento usam `next/image` com `unoptimized` para object URLs locais.

## Segurança

- Cabeçalhos presentes em todas as rotas: CSP com `default-src 'self'`, `object-src 'none'`, `frame-ancestors 'none'`, `base-uri 'self'` e `form-action 'self'`; `X-Content-Type-Options: nosniff`; `X-Frame-Options: DENY`; `Referrer-Policy: strict-origin-when-cross-origin`; `Permissions-Policy`; `Cross-Origin-Opener-Policy: same-origin`; HSTS em produção.
- Cookies de sessão HttpOnly e SameSite=Lax, com Secure em HTTPS ou `x-forwarded-proto: https`. Teste e2e confirma que `document.cookie` não expõe `sp_session`, `sp_refresh` nem `sp_csrf`.
- Nenhum `dangerouslySetInnerHTML`, `innerHTML`, token em storage ou `eval` em código de produção. O portão `check-security` falha se aparecer.
- 401 leva ao login com destino preservado. 403 leva à recusa de acesso. 429 respeita `Retry-After`, mostra toast traduzido e tenta novamente uma vez quando a espera é de até 60 s.
- CSP mantém `'unsafe-inline'` em `script-src` por causa dos scripts inline do runtime do Next. A evolução para nonce fica registrada como risco residual.
- `npm audit --audit-level=critical` passou. As 7 ocorrências moderadas são transitivas de `typescript-eslint` (`minimatch`) e ficam em dependências de desenvolvimento.

## Testes e regressão visual

- Fluxos críticos verdes: login e sessão, upload e dossiê, filtros e paginação, notificações, conta e pagamentos.
- Screenshots de regressão visual com baseline em dois temas: `e2e/visual-regression.spec.ts-snapshots/landing-light-chromium-win32.png`, `landing-dark`, `painel-light` e `painel-dark`.
- Viewport dos screenshots: 1280 x 900, movimento reduzido, relógio fixo e animações desligadas.

## Observabilidade

- Integração opcional por `NEXT_PUBLIC_SENTRY_DSN`. Sem DSN, o SDK não é baixado e nada é enviado.
- Coleta desligada para cookies, cabeçalhos, corpos, query string, usuário e dados de IA.
- Evento reconstruído apenas com exceção sanitizada e tags seguras. E-mails, CPF, CNPJ, telefone, Bearer, token e query sensível são redigidos.
- Testes unitários cobrem configuração, recusa de DSN inseguro, redação de PII, descarte de `request`, `user`, `extra`, `contexts` e `breadcrumbs`.

## Limitações conhecidas

- Lighthouse é medição de laboratório local, não dado de campo (CrUX).
- O aviso de depreciação de `middleware.ts` no Next 16 continua e não bloqueia a entrega.
- A integração Sentry só foi validada por testes unitários e por ausência de carregamento sem DSN; nenhum evento real foi enviado. Com DSN, a origem do Sentry entra em `connect-src` no momento do build.
- As baselines de regressão visual são do Chromium no Windows (`-win32`). Em outro sistema operacional, gere novamente com `npx playwright test e2e/visual-regression.spec.ts --update-snapshots`.
- O deploy na Vercel não foi executado neste ambiente. A configuração, as variáveis e os cabeçalhos estão documentados no README e em `vercel.json`.

## O que não foi tocado

- Backend FastAPI, migrations, Docker Compose, banco, infraestrutura e knowledge base.
- Nenhum arquivo fora de `frontend/`.
- Nenhuma rota, funcionalidade de negócio ou contrato de API novo.
