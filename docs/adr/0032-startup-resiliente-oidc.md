# ADR 0032: configuracao do Google OIDC nao derruba o processo

- Status: aceito
- Data: 2026-11-25

## Contexto

Em 2026-11-25 a API no Railway passou a responder `502 Application failed to respond` em todas as rotas. O processo morria antes de abrir a porta, porque `get_settings()` roda no import do modulo `paysentineliq.interface.api.main` e a validacao adicionada no commit `8e5358f` levantava erro quando `GOOGLE_REDIRECT_URI` divergia de `/api/v1/auth/google/callback`. O valor em producao ainda era o legado `https://sentinelpay.up.railway.app/api/auth/google/callback`.

Reproducao local com o mesmo valor:

```
ValidationError: 1 validation error for Settings
  Value error, GOOGLE_REDIRECT_URI must target /api/v1/auth/google/callback
```

Consequencia: o deploy subia um container que encerrava imediatamente, e o proxy do Railway devolvia 502 em 2 a 27 ms para qualquer rota, inclusive `/health`.

## Decisao

1. Credenciais do Google (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`) e `FRONTEND_URL` deixam de ser requisitos de boot. Elas continuam necessarias para o login Google funcionar, mas nao para o processo iniciar.
2. A validacao do callback vira uma propriedade derivada (`google_redirect_uri_valid`) que exige `https` fora de local e o caminho `/api/v1/auth/google/callback`. Valor ausente, divergente ou legado apenas desabilita o login Google.
3. `create_app` emite um unico aviso `google_oidc_not_configured` com os nomes das variaveis faltantes, sem valores.
4. `GET /api/v1/auth/google/login` e `GET /api/v1/auth/google/callback` usam uma dependencia `require_google_configured` que responde `503 auth_not_configured` com mensagem explicita antes de tocar em Redis, Authlib ou estado do app.
5. As demais rotas seguem normais: `/health`, `/ready`, `/api/v1/auth/capabilities`, `/api/v1/auth/password-policy` e o login por senha nao dependem de Google.

O caminho oficial do callback permanece `/api/v1/auth/google/callback`. Nao foi criado alias para o caminho legado `/api/auth/...`, para manter um unico contrato e evitar duas URIs no Google Console.

## Alternativas descartadas

- Manter a validacao fatal e exigir a variavel correta antes do deploy. Rejeitada porque uma variavel de uma funcionalidade opcional nao deve impedir health check, login por senha e rotas de produto de subirem.
- Aceitar qualquer `GOOGLE_REDIRECT_URI`. Rejeitada porque o Google exige correspondencia exata e um valor errado geraria falha silenciosa no consentimento.
- Registrar `SessionMiddleware` do Starlette para o state do OIDC. Desnecessario: o state e o PKCE ficam no Redis e no cookie `oidc_state`, e nenhuma rota usa `request.session`.

## Consequencias

- Um deploy com configuracao Google errada agora fica no ar, com o aviso no log e o login Google desabilitado, em vez de derrubar todo o servico.
- O operador precisa conferir `GOOGLE_REDIRECT_URI` e `FRONTEND_URL` para reativar o login, sem redeploy de codigo se a mudanca for apenas de variavel.
- `/api/v1/auth/capabilities` passa a ser a forma barata de confirmar se o login Google esta ativo em producao.
