# SPEC 0026: autenticação por e-mail e senha

- Fase: P20
- Data: 2026-11-23
- Depende de: SPEC 0007 (auth Google), ADR 0029 e ADR 0030

## Diagnóstico

- Sessão única: access JWT HS256, refresh opaco rotativo com hash em `refresh_tokens` e família
  revogada em reuso. Cookies HttpOnly emitidos pela API e espelhados pelo BFF.
- `users` tem `google_sub` obrigatório, e-mail sem unicidade case-insensitive e nenhuma coluna de
  senha. Não existe cadastro, login por credenciais, verificação, recuperação nem consentimento
  persistido.
- Rate limit Token Bucket global por IP, brute force por IP e identificador em Redis, logs com
  filtro de PII e problem+json como formato de erro.
- Já existe `EmailPort`, adaptador SMTP e Mailpit no Compose; a entrega de notificações roda em
  worker Celery. O e-mail transacional de auth usa a mesma porta, com um emissor de desenvolvimento
  que grava em arquivo e log somente fora de produção.
- Não existe provedor de e-mail contratado nem domínio remetente definido.

## Decisões

1. Senha usa Argon2id configurável com rehash no login. Política mínima de 10 e máxima de 128
   caracteres, bloqueio de senhas comuns e de senha que contenha e-mail ou nome. Fonte da verdade
   no servidor, exposta por `GET /api/v1/auth/password-policy`.
2. Tokens de verificação e reset são opacos, gerados com `secrets.token_urlsafe(32)`, guardados
   apenas como SHA-256, com expiração (24 h e 30 min), uso único, IP e user agent de criação.
3. Feature flag `AUTH_PASSWORD_ENABLED`, desligada por padrão. Sem provedor de e-mail pronto, o
   cadastro fica indisponível e as rotas respondem 503 `auth_not_configured`; nunca fingir envio.
4. Cadastro, forgot e resend devolvem 202 com a mesma mensagem e tempo equalizado. Login devolve
   sempre 401 `invalid_credentials`, exceto conta com senha correta e e-mail não verificado
   (403 `email_not_verified`) e bloqueio comprovado por senha correta (429 com `Retry-After`).
5. Bloqueio progressivo por conta em `locked_until`, sem revelar estado sem senha correta; o
   rate limit por IP e e-mail continua sendo a primeira barreira.
6. Vinculação Google: só vincula `google_sub` a conta existente quando o e-mail local está
   verificado e o Google devolve `email_verified=true`. Caso contrário, login Google falha de
   forma genérica e registra evento, impedindo pré-sequestro.
7. `legal_consents` guarda termos e privacidade por usuário, versão `1.1` e IP/user agent. O
   primeiro acesso Google passa a registrar consentimento implícito com origem `google_signin`.
8. `auth_events` registra cadastro, login, falha, bloqueio, verificação, reset, troca e logout sem
   senha, token ou hash. E-mails completos não entram em log, trace ou evento.
9. E-mails usam `APP_BASE_URL` fixo, templates pt-BR/en/es em HTML e texto puro, enviados fora do
   caminho crítico por BackgroundTasks com até 3 tentativas e log seguro.
10. Exclusão de conta remove usuário, senha, tokens e consentimentos por cascata; eventos de
    segurança ficam com `user_id` nulo para a guarda legal, conforme rotina documentada.

## Critérios de aceite

- Cadastro cria usuário com hash Argon2id, consentimentos e token de verificação; duplicado não
  cria conta e dispara aviso ao dono, sempre com resposta neutra.
- Login emite o mesmo par de tokens e cookies do Google e recusa senha errada, inexistente e
  conta só-Google com mensagem idêntica.
- Verificação e reset consomem token único e inválido/expirado/reutilizado devolve erro genérico.
- Reset e troca de senha revogam os refresh tokens do usuário.
- Google vincula apenas conta verificada e não vincula conta não verificada.
- Rate limit e bloqueio progressivo devolvem 429 com `Retry-After`.
- Nenhum log, evento ou resposta contém senha, hash ou token.
- Testes unitários, de integração e de rotas cobrem os cenários acima.
