# SPEC 0004: Autenticacao Google OIDC, JWT e RBAC

## Objetivo
Permitir login exclusivamente via Google OIDC (authorization code + PKCE), emissao de access JWT curto e refresh opaco rotativo, com autorizacao por papel e o dono dos dados sempre vindo do token. Sem cadastro por senha e sem telas.

## Requisitos (RF) e nao funcionais (RNF)
- RF1: Authlib para o fluxo OAuth2/OIDC e `joserfc` para JWT; `authlib.jose` esta depreciado na versao instalada.
- RF2: `GET /api/v1/auth/google/login` gera state, nonce e PKCE S256; state e nonce sao de uso unico e ficam no Redis com TTL curto; state e vinculado ao navegador por cookie HttpOnly.
- RF3: `GET /api/v1/auth/google/callback` valida state (cookie + Redis), nonce, `iss`, `aud`, `exp` e `email_verified` antes de criar a sessao.
- RF4: `POST /api/v1/auth/refresh` exige CSRF, rotaciona o refresh e devolve novo access token; reuso de refresh revoga toda a familia.
- RF5: `POST /api/v1/auth/logout` exige CSRF, revoga a familia do refresh e coloca o `jti` do access atual na lista de revogados no Redis ate `exp`.
- RF6: access JWT HS256 fixo, claims `sub`, `role`, `jti`, `exp`, `iat`; verificacao rejeita `none`, troca de algoritmo, assinatura invalida, expiracao e `jti` revogado.
- RF7: refresh e um token opaco de alta entropia; apenas o hash SHA-256 e persistido; cookie HttpOnly, Secure fora de local, SameSite=Lax, com dominio configuravel.
- RF8: tabelas `users` e `refresh_tokens` via migration 0002, sempre precedida de backup nao vazio.
- RF9: `GET /api/v1/users/me` retorna o perfil do usuario do JWT; `get_current_user` carrega o usuario pelo `sub`; `require_role` aceita `user` e `admin`.
- RF10: rotas de exemplo protegidas recusam anonimo (401), aceitam `user` e recusam `user` em rota `admin` (403).
- RF11: integrar rate limit, CSRF e forca bruta nas rotas de auth.
- RNF1: nenhuma credencial real do Google em testes; fluxo real marcado como NAO VALIDADO.
- RNF2: sem PII/token em logs, cookies de refresh nunca legiveis por JS, senhas nunca existem.
- RNF3: user_id sempre de `sub` do JWT, nunca de body/URL; toda consulta de dados do usuario filtra pelo dono.

## Fora do escopo
Cadastro por senha, recuperacao de senha, telas, MFA, administracao de usuarios, autorizacao fina por recurso alem de role, refresh token do Google para chamadas a APIs Google.

## Contrato (endpoints, cookies, erros)
- `GET /api/v1/auth/google/login` -> 302 para Google; seta `oidc_state` HttpOnly e salva state no Redis.
- `GET /api/v1/auth/google/callback?code&state` -> valida tudo, seta `refresh_token` HttpOnly e `csrf_token` legivel, limpa `oidc_state` e redireciona para `FRONTEND_URL`.
- `POST /api/v1/auth/refresh` (cookie `refresh_token` + header `X-CSRF-Token`) -> 200 `{access_token, token_type, expires_in, user}`; seta novo refresh e novo CSRF.
- `POST /api/v1/auth/logout` (CSRF) -> 204; cookies limpos; refresh revogado e access `jti` na blocklist.
- `GET /api/v1/users/me` (Bearer) -> perfil do usuario do token.
- `GET /api/v1/protected/user` (Bearer) -> 200 para qualquer autenticado; `GET /api/v1/protected/admin` (Bearer) -> 200 somente admin.
- Erros: problem+json com `code` (`invalid_state`, `google_auth_failed`, `email_not_verified`, `invalid_refresh_token`, `refresh_token_reuse`, `invalid_access_token`, `forbidden`, `too_many_attempts`), sem detalhes sensiveis.
- Cookies: refresh `HttpOnly`, `Secure` fora de local, `SameSite=Lax`, `Path=/api/v1/auth`, `Max-Age` da TTL; CSRF legivel, `Path=/`, mesmo dominio configuravel; `oidc_state` HttpOnly e curto.

## Criterios de aceite (cada um vira pelo menos um teste)
1. Access JWT valido autentica; token adulterado, expirado, com `alg=none` ou outro algoritmo e `jti` revogado sao recusados.
2. Login gera state, nonce e PKCE; callback com state invalido/ausente/expirado falha e nao cria usuario.
3. ID token do Google mockado: iss/aud/exp/nonce/assinatura/email_verified invalidos falham.
4. Callback valido cria/atualiza usuario por `google_sub`, seta cookies e redireciona sem tokens na URL.
5. Refresh valido rotaciona; token antigo reutilizado revoga a familia e falha; refresh expirado/desconhecido falha.
6. Refresh/logout sem CSRF falham com 403 `csrf_invalid`.
7. Logout limpa cookies, revoga familia e bloqueia o `jti` do access.
8. `users/me` exige Bearer e retorna o usuario do `sub`; user nao acessa rota admin.
9. Migration cria `users` e `refresh_tokens`; backup antes da migration existe e nao esta vazio.
10. Rate limit e forca bruta bloqueiam abuso nas rotas de auth (429 com `Retry-After`).
11. Checklist OWASP A01/A02/A07 atualizado.

## Casos de borda e de abuso
- State replay, state de outro navegador, nonce ausente, code reutilizado, email nao verificado, conta Google sem email/name.
- Token JWT com `alg=none`, HS512, assinatura alterada, `sub`/`role`/`jti` ausentes ou malformados, expirado, `jti` revogado.
- Refresh reutilizado concorrentemente (row lock), refresh de outra familia, cookie ausente, cookie de outro dominio.
- CSRF ausente/incorreto, Origin externa, cookie de refresh expirado.
- Redis indisponivel em auth: fail-closed (503), sem aceitar token possivelmente revogado.
- Role adulterada no token nao eleva privilegio: autorizacao usa o usuario carregado do banco.

## Plano de testes (TDD: teste falho primeiro)
1. JWT: emitir/decodificar, claims, expiracao, algoritmo, assinatura e blocklist.
2. OIDC: URL/PKCE/state/nonce, token exchange mockado e verificacao de ID token com JWKS mockado.
3. AuthService: upsert, rotacao, reuso, logout e familia.
4. Rotas: login/callback/refresh/logout/me/protegidas com Google, estado e servicos fake; CSRF e forca bruta.
5. Integracao: migration, repositorios, rotacao/reuso no Postgres real e backup.
6. Rodar `make check`, `make test-docker`, `make bandit`, `make audit`; atualizar OWASP.

## Riscos e NAO VALIDADO
- Fluxo real com o Google nao sera executado (sem credenciais reais); validacao fica por mocks e JWKS local.
- Endpoints oficiais do Google sao configuracao fixa; mudancas de contrato exigem revisao.
- Authlib 1.9.5 usa a integracao `httpx` marcada como deprecated em favor de `httpx2`; a biblioteca ainda funciona, mas o upgrade precisa ser reavaliado.
- Rotacao de refresh concorrente depende do row lock do PostgreSQL; teste de concorrencia real e recomendado.
- Sem MFA, sem recuperacao de conta e sem revogacao global de todas as sessoes do usuario.
