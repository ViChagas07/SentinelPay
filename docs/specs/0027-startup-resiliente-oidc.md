# SPEC 0027: startup resiliente da API e configuracao do Google OIDC

## Contexto

Depois do commit `8e5358f`, a API no Railway passou a responder `502 Application failed to respond` em todas as rotas, inclusive `/health`. O processo morre durante o import porque `get_settings()` roda no import do modulo `paysentineliq.interface.api.main` e a nova validacao `GOOGLE_REDIRECT_URI must target /api/v1/auth/google/callback` levanta `pydantic_core.ValidationError` antes de o uvicorn abrir a porta.

## Objetivo

1. Fazer o app subir mesmo quando a configuracao do Google estiver ausente ou inconsistente.
2. Manter as rotas que nao dependem do Google funcionando (`/health`, `/ready`, `/api/v1/auth/capabilities`, `/api/v1/auth/password-policy`, login por senha).
3. Responder `503 auth_not_configured` com mensagem explicita apenas em `/api/v1/auth/google/login` e `/api/v1/auth/google/callback`.

## Decisao

- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` e `GOOGLE_REDIRECT_URI` deixam de ser obrigatorios no `Settings` fora de local. O valor invalido nao derruba o processo: vira configuracao incompleta, e `google_configured` continua sendo o portao usado pelas rotas.
- A validacao de `FRONTEND_URL` e `GOOGLE_REDIRECT_URI` passa a ser tolerante: `GOOGLE_REDIRECT_URI` so precisa ser `https` e apontar para o caminho do callback quando estiver preenchido; `FRONTEND_URL` so precisa ser `https` quando estiver preenchido.
- O `Settings` registra um aviso estruturado `google_oidc_not_configured` com os nomes das variaveis faltantes no momento em que `google_configured` for falso e `APP_ENV` nao for local, sem imprimir valores.
- `AuthNotConfiguredError` passa a explicar que a autenticacao Google nao esta configurada.
- A documentacao de producao em `.env.example` e `README.md` lista todas as variaveis obrigatorias.

## Fora de escopo

- Trocar o caminho `/api/v1` por `/api/auth` ou vice-versa.
- Alterar modelos, pipeline de IA, design ou o BFF do front.
- Reintroduzir `SessionMiddleware` do Starlette. O fluxo atual guarda o state do OIDC no Redis e no cookie `oidc_state`, nao em sessao de servidor; nenhuma rota usa `request.session`.

## Criterios de aceite

- Importar `paysentineliq.interface.api.main` com `APP_ENV=production` e sem variaveis do Google nao levanta excecao.
- `GET /health` responde `200` sem variaveis do Google.
- `GET /api/v1/auth/capabilities` responde `200` com `google_enabled=false`.
- `GET /api/v1/auth/password-policy` responde `200`.
- `GET /api/v1/auth/google/login` responde `503` com `code=auth_not_configured`.
- Com `GOOGLE_REDIRECT_URI` valido, `GET /api/v1/auth/google/login` responde `302` para `accounts.google.com` com o `redirect_uri` https e o caminho `/api/v1/auth/google/callback`.
- `poetry run pytest -m "not docker"` e `make check` verdes.
