# ADR 0007: Autenticacao Google OIDC, JWT e sessoes

- Status: aceito
- Data: 2026-11-14

## Contexto
A P04 precisa de login sem senha, sessao curta para a API, refresh revogavel e autorizacao por papel. O frontend futuro sera separado da API. O fluxo OIDC exige protecao contra login CSRF, replay de code e tokens forjados. A versao instalada do Authlib (1.9.5) emite `AuthlibDeprecationWarning` para `authlib.jose` e recomenda `joserfc`; o joserfc 1.8.0 ja vem como dependencia.

## Decisao
- **Transporte**: access token em `Authorization: Bearer`; refresh em cookie `HttpOnly`, `Secure` fora de local, `SameSite=Lax`, `Path=/api/v1/auth`, com `Domain` configuravel para compartilhamento entre subdominios. CSRF double-submit (`csrf_token` legivel + `X-CSRF-Token`) em refresh/logout.
- **JWT**: HS256 fixo na emissao e verificacao, secret de pelo menos 32 bytes; claims `sub`, `role`, `jti`, `exp`, `iat`. `joserfc` e usado para JWT/ID token porque `authlib.jose` esta depreciado. A verificacao passa `algorithms=["HS256"]` (access) ou `["RS256"]` (ID token Google), rejeitando `none` e troca de algoritmo. `jti` revogado fica no Redis ate `exp`; Redis indisponivel em auth falha fechado.
- **OIDC**: Authlib `AsyncOAuth2Client` monta a URL com PKCE S256 e troca o code; o ID token e verificado com joserfc contra JWKS do Google, validando assinatura, `iss`, `aud`, `exp`, `nonce` e `email_verified`. State e nonce sao aleatorios e de uso unico; state fica no Redis com TTL e e vinculado ao navegador por cookie HttpOnly. Nenhum token e colocado na URL de redirect.
- **Refresh**: token opaco de alta entropia, somente SHA-256 no banco, familia UUID, expiracao e revogacao. Cada refresh le a linha com `FOR UPDATE`, revoga o token atual e cria o proximo na mesma familia. Reuso de token revogado revoga a familia inteira. Logout revoga a familia e bloqueia o `jti` do access.
- **Identidade**: usuario e criado/atualizado por `google_sub` unico. `role` padrao `user`; `admin` e atribuido fora do fluxo. `preferred_locale` padrao `pt-BR` e `timezone` padrao `America/Sao_Paulo`. O `user_id` de qualquer consulta vem do `sub` do JWT; `require_role` usa o usuario carregado do banco (fonte de verdade), nao apenas a claim.
- **Defesas**: rate limit em todas as rotas `/api/v1` (auth incluso), CSRF em refresh/logout, forca bruta por IP e identificador em callback/refresh, cookies limpos em falha, logs sem token/email.

## Alternativas consideradas
- Refresh em localStorage: descartado; exposto a XSS.
- Access token em cookie: descartado; CSRF em toda a API e maior superficie.
- RS256 com chave propria agora: descartado por exigir gestao de chaves; HS256 com secret forte e suficiente para a fase.
- Authlib JOSE: descartado por deprecacao; joserfc e a recomendacao oficial.
- State apenas em cookie assinado: descartado; state no Redis permite uso unico e TTL central.
- Role apenas da claim: descartado para evitar privilegio residual; o banco e a fonte de verdade.
- Refresh sem rotacao: descartado; rotacao + deteccao de reuso reduz dano de vazamento.

## Consequencias
- O frontend precisa ler o cookie CSRF e enviar `X-CSRF-Token`; em subdominios diferentes, `COOKIE_DOMAIN` deve ser configurado.
- O fluxo real com Google nao foi executado sem credenciais; testes usam JWKS/token mockados.
- Authlib 1.9.5 ainda usa a integracao `httpx` marcada como deprecated em favor de `httpx2`; upgrade deve ser reavaliado.
- Refresh rotativo exige row lock e transacao; falha de Redis em auth resulta em 503.
- Nao ha MFA nem revogacao global; adicionar em fase propria se necessario.
