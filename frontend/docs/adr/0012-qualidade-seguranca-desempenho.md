# ADR 0012: Qualidade, segurança de borda e desempenho

- Status: aceito
- Data: 2026-11-16
- Fase: F11

## Contexto

A revisão final precisava de portões automáticos para i18n, dados fictícios, travessão longo e padrões inseguros, além de cabeçalhos de segurança, tratamento de 401/403/429, carregamento tardio do visualizador e dos gráficos, medição de bundle e Lighthouse, observabilidade opcional e configuração de deploy.

## Decisões

1. Portões de conteúdo em `scripts/check-i18n.mjs`, `scripts/check-forbidden-content.mjs` e `scripts/check-security.mjs`, executados por `npm run check:content` dentro de `npm run check`.
2. O dicionário é a única fonte de texto de interface. O script compara chaves e placeholders entre pt, es e en e falha se houver locale extra ou texto JSX fixo. O catálogo interno `/dev/design` e a imagem Open Graph ficam fora da varredura porque não são interface de produção.
3. A varredura de dados fictícios cobre apenas código de produção; testes e documentação podem citar `mock` e fixtures.
4. Cabeçalhos de segurança em `next.config.ts` para todas as rotas, com CSP sem `unsafe-eval` em produção, `frame-ancestors 'none'`, `object-src 'none'` e HSTS fora de desenvolvimento. O `vercel.json` repete apenas os cabeçalhos simples de borda; a CSP fica em um único lugar.
5. Cookies de sessão continuam `HttpOnly` e `SameSite=Lax`, com `Secure` quando a requisição é HTTPS ou traz `x-forwarded-proto: https`. Nenhum token é exposto ao JavaScript.
6. O usuário inicial do shell é buscado no servidor em `lib/session/server-user.ts`, com timeout de 2,5 s e fallback para a busca no cliente. O token sai do cookie no servidor e nunca é serializado para o navegador.
7. A transição de página não anima opacidade. A opacidade inicial impedia o título do servidor de virar LCP e atrasava a métrica em cerca de 4 s na simulação móvel.
8. Visualizador de documento e gráficos são carregados com `next/dynamic` e `ssr: false`, exibindo skeleton acessível no lugar.
9. 429 passa por um interceptor global que mostra aviso traduzido com `Retry-After` e a consulta tenta novamente uma vez quando a espera é de até 60 s. 401 leva ao login e 403 à recusa de acesso já existentes.
10. Observabilidade é opcional por `NEXT_PUBLIC_SENTRY_DSN`. O SDK é importado dinamicamente, coleta desligada (`dataCollection`) e o evento é reconstruído só com exceção sanitizada e tags seguras. Nenhum corpo de requisição, documento ou PII é enviado.
11. O orçamento de bundle é 280 kB de JavaScript gzip por rota, medido por `npm run analyze` a partir dos manifests de build.
12. Lighthouse roda contra build de produção com sessão real de teste e falha abaixo de 90 em desempenho, acessibilidade e boas práticas.

## Consequências

- `script-src` mantém `'unsafe-inline'` porque o runtime do Next injeta scripts inline. A evolução para nonce exige middleware dedicado e fica registrada como risco residual.
- O Lighthouse é uma medição de laboratório local, não uma garantia de campo.
- Sem DSN configurado, nenhum SDK de observabilidade é carregado e nenhum evento é enviado.
- O aviso de depreciação da convenção `middleware.ts` do Next 16 continua conhecido e não bloqueia a entrega.
