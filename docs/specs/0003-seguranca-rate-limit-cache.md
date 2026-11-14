# SPEC 0003: Seguranca reutilizavel, rate limit e cache SWR

## Objetivo
Adicionar camadas de protecao reutilizaveis para todas as fases seguintes, cada uma com teste de abuso, e preencher o checklist OWASP com evidencia real. Sem autenticacao de usuario nesta fase.

## Requisitos (RF) e nao funcionais (RNF)
- RF1: rate limit Token Bucket atomico em Redis via Lua, por IP e por usuario quando `request.state.user_id` existir. Capacidade e reposicao vem do ambiente. Excesso retorna 429 problem+json com `Retry-After`.
- RF2: falha do Redis no rate limit e fail-open com log estruturado, exceto `/api/v1/auth/*`, que falha fechado com 503 problem+json.
- RF3: cache generico Stale-While-Revalidate com TTL macio/duro, jitter, lock unico (`SET NX EX`) e servico de valor velho para quem perde o lock.
- RF4: cabecalhos de seguranca em todas as respostas; HSTS somente fora de `APP_ENV=local`; CSP restritiva para API; TrustedHost e CORS com allowlist explicita, sem `*` com credenciais.
- RF5: CSRF double-submit para fluxos baseados em cookie; Bearer puro nao exige CSRF. Token de cookie legivel e token de header comparados em tempo constante.
- RF6: guarda SSRF para URLs de saida configuraveis: HTTPS em producao, bloqueio de IPs privados/loopback/link-local/metadados, resolucao DNS, redirects validados por salto e conexao fixada no IP validado.
- RF7: allowlist de infraestrutura fixa (ex.: LM Studio local) separada de URLs de usuario.
- RF8: servico de forca bruta no Redis com contadores por IP e identificador, janela e backoff exponencial com bloqueio temporario.
- RF9: limite de corpo, timeout de requisicao, limite de tamanho de texto e validador reutilizavel que rejeita HTML/controle.
- RF10: SQL apenas por ORM/queries parametrizadas; teste com payloads classicos nos filtros existentes. Respostas sempre JSON/problem+json.
- RF11: `pip-audit` e `bandit` no Makefile e executados.
- RNF1: sem auth, sem tabelas de negocio, sem declarar protecao contra DDoS de borda.
- RNF2: nenhum IP, usuario, token ou dado pessoal bruto em logs; identificadores de rate limit/forca bruta sao pseudonimizados em chaves Redis.

## Fora do escopo
Login, refresh token, autorizacao, JWT, tabelas de negocio, WAF/CDN, metricas Prometheus e frontend.

## Contrato (endpoints, headers, erros)
- Rate limit excedido: `429 application/problem+json`, `code=rate_limited`, `Retry-After` em segundos, `X-Request-ID`.
- Rate limit indisponivel em auth: `503 application/problem+json`, `code=rate_limit_unavailable`.
- Respostas incluem `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, CSP `default-src 'none'; frame-ancestors 'none'; base-uri 'none'`; HSTS fora de local.
- CORS: apenas origens da allowlist, credenciais permitidas, sem curinga.
- CSRF: cookie `csrf_token` + header `X-CSRF-Token`; ausente/diferente -> `403 csrf_invalid`.
- SSRF: URL bloqueada -> `400 ssrf_blocked`; redirects sao revalidados; allowlist de infraestrutura so vale para hosts configurados.
- Corpo acima do limite -> `413 request_too_large`; timeout -> `504 request_timeout`; texto com HTML -> `422 validation_error`.
- `GET /health` e `GET /ready` ficam fora do rate limit.

## Criterios de aceite (cada um vira pelo menos um teste)
1. Token Bucket atomico: 20 chamadas concorrentes com capacidade 5 geram exatamente 5 permitidas (teste docker com Redis).
2. Middleware retorna 429 com `Retry-After` e nao chama a rota; Redis fora em rota normal faz fail-open; em `/api/v1/auth/*` retorna 503.
3. Cache SWR: com valor velho e lock, 20 chamadas concorrentes geram 1 recomputacao; perdedores recebem valor velho.
4. Cabecalhos presentes em sucesso e erro; HSTS ausente em local e presente fora; CORS aceita allowlist e rejeita origem externa; TrustedHost rejeita Host invalido.
5. CSRF: sem cookie/header, cookie sem header, header diferente -> 403; par valido -> 200 (rota de teste).
6. SSRF: IP privado, loopback, link-local, metadados, credenciais na URL, HTTP em producao e redirect para IP privado sao bloqueados; host publico e allowlist de infraestrutura valida passam.
7. Forca bruta: N falhas bloqueiam por IP e identificador; `reset` libera; bloqueio expira.
8. Corpo grande -> 413; rota lenta -> 504; texto com `<script>` -> 422; texto simples valido passa.
9. SQLi: payloads classicos na rota/filtro existente nao alteram o schema nem executam SQL; respostas sao 422 problem+json.
10. `pip-audit` e `bandit` rodam; achados sao tratados ou registrados como NAO VALIDADO.
11. Checklist OWASP preenchido com referencia a testes e pendencias reais.

## Casos de borda e de abuso
- Rate limit concorrente e chaves expiradas; Redis indisponivel; usuario autenticado futuro; IP atras de proxy (nao confiar em header sem proxy confiavel).
- Cache com lock expirado, hard miss, jitter e servidor lento.
- CORS com `Origin` maliciosa; Host header invalido; preflight.
- CSRF com token de outro usuario/cookie, token vazio, comparacao parcial.
- SSRF com DNS rebinding, multiplos IPs, IPv6, redirects encadeados, portas nao padrao, `file://`, `gopher://`, `http://169.254.169.254`.
- Forca bruta com identificadores diferentes no mesmo IP e vice-versa.
- HTML em texto, corpo chunked, Content-Length mentiroso, payloads SQLi e XSS.

## Plano de testes (TDD: teste falho primeiro)
1. Rate limit: unitario do middleware/limiter + concorrencia com Redis.
2. SWR: concorrencia com Redis e valor velho.
3. Headers/CORS/TrustedHost/limites/timeout/sanitizer: unitarios com app de teste.
4. CSRF e forca bruta: unitarios + Redis.
5. SSRF: unitarios com resolver e transporte falsos; backend pinado testado isoladamente.
6. SQLi/XSS: integracao com API + verificacao do schema.
7. Rodar `make check`, `make test-docker`, `pip-audit` e `bandit`; preencher checklist.

## Riscos e NAO VALIDADO
- DDoS de volumetria e borda (CDN/WAF) nao implementado: NAO VALIDADO; o app so oferece rate limit, corpo e timeout.
- Auth e autorizacao ainda nao existem: A01/A07 ficam parciais/NAO VALIDADO ate a P04.
- Metricas de rate limit/forca bruta sao logs estruturados; nao ha backend de metricas/alertas nesta fase.
- IP atras de proxy exige configuracao de proxy confiavel; sem isso, usa-se o IP da conexao.
- DNS rebinding e mitigado por conexao fixada no IP validado, mas apenas o primeiro IP resolvido e usado por tentativa.
- A allowlist de infraestrutura deve ser revisada por ambiente; nunca incluir hosts controlados pelo usuario.
