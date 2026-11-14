# ADR 0006: Camadas de protecao reutilizaveis

- Status: aceito
- Data: 2026-11-14

## Contexto
A P03 precisa proteger rotas futuras contra abuso sem introduzir autenticacao. As protecoes devem ser reutilizaveis, testaveis e nao criar falsa sensacao de seguranca de borda. Redis e a infraestrutura compartilhada para rate limit, cache e forca bruta; PostgreSQL continua sendo a fonte de verdade.

## Decisao
- Rate limit: Token Bucket em Lua, atomico no Redis, com capacidade e reposicao por ambiente. Chaves por IP e por usuario futuro sao pseudonimizadas com HMAC/SHA-256 antes de ir ao Redis. Falha do Redis e fail-open com log estruturado, exceto `/api/v1/auth/*`, que falha fechado com 503.
- Cache: utilitario generico SWR com TTL macio e duro, jitter, lock unico `SET NX EX` e liberacao compare-and-delete. Quem perde o lock recebe o valor velho; hard miss aguarda o preenchimento ate um timeout. Chaves sao hasheadas; valores so podem conter dados derivados e nao pessoais.
- Cabecalhos: middleware unico adiciona `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` e CSP restritiva. HSTS e habilitado fora de `APP_ENV=local`. TrustedHost e CORS usam allowlists explicitas; CORS nunca aceita `*` com credenciais.
- CSRF: double-submit cookie para fluxos baseados em cookie. O cookie `csrf_token` e legivel (nao HttpOnly), o header `X-CSRF-Token` e comparado em tempo constante. Bearer puro nao usa CSRF.
- SSRF: guarda valida esquema, credenciais, porta, DNS e IPs; bloqueia faixas nao globais e metadados de nuvem. Redirects sao validados por salto. A conexao e fixada no IP validado com um `AsyncNetworkBackend` do httpcore, reduzindo rebinding entre a resolucao e o TCP. Hosts de infraestrutura fixa entram em allowlist explicita e separada de URLs de usuario.
- Forca bruta: contadores Redis por IP e identificador, pseudonimizados, com janela, backoff exponencial e bloqueio temporario. Falha do Redis e fail-closed para fluxos de auth.
- Limites: corpo maximo, timeout de requisicao, tamanho maximo de texto e validador que rejeita HTML/controle. SQL continua apenas por ORM/parametros vinculados.
- Auditoria: `pip-audit` e `bandit` no Makefile. Achados sao registrados no checklist OWASP; ausencia de achado nao e garantia de seguranca.

## Alternativas consideradas
- Rate limit em memoria: descartado por nao funcionar com multiplos workers/instancias.
- Janela fixa: descartado por rajadas na borda da janela; Token Bucket suaviza.
- Cache sem lock: descartado por Cache Stampede/Thundering Herd.
- CSP com `unsafe-inline`: descartado; a API nao serve HTML.
- `*` em CORS com credenciais: descartado por inseguro.
- CSRF para Bearer: descartado; Bearer nao e enviado automaticamente pelo navegador.
- Bloqueio de SSRF apenas por regex de URL: descartado; e necessario resolver DNS e validar IPs.
- Depender de WAF/CDN para rate limit: descartado como unica defesa; o app tambem limita.

## Consequencias
- Redis passa a ser critico para protecao; a indisponibilidade e tratada explicitamente e monitorada por log. Em auth, indisponibilidade bloqueia acesso.
- Rate limit e forca bruta compartilham Redis e precisam de limpeza/observabilidade.
- O SafeHttpClient usa APIs internas do httpx/httpcore para pinagem de IP; versoes estao fixadas e a integracao deve ser reavaliada em upgrades.
- A allowlist de infraestrutura e um ponto sensivel: nunca deve conter hosts controlados pelo usuario.
- Nao ha protecao de DDoS de volumetria; CDN/WAF continua NAO VALIDADO.
- Auth/autorizacao seguem fora do escopo; A01/A07 do OWASP ficam parciais.
