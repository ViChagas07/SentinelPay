# ADR 0017: autenticação por senha atrás de capacidades e BFF

- Status: aceito
- Data: 2026-11-23
- Fase: F16

## Contexto

O backend passa a oferecer cadastro e login por senha, mas a produção pode não ter SMTP
configurado. O front precisa esconder a interface sem simular sucesso e sem expor tokens.

## Decisão

1. A tela consulta `GET /api/v1/auth/capabilities` no servidor Next e recebe
   `{ password_enabled, signup_enabled, password_reset_enabled, google_enabled }`. O login por senha
   depende só de `password_enabled`; cadastro e recuperação dependem do provedor de e-mail. Falha de
   rede ou resposta inválida desliga tudo e mantém o Google, então o login atual continua funcionando.
2. Todos os fluxos novos passam pelo BFF. O BFF valida a origem, encaminha apenas cabeçalhos
   necessários, aplica os cookies HttpOnly existentes e nunca devolve tokens ao navegador.
3. O login por senha reaproveita o mesmo mecanismo de sessão do Google: access em cookie
   `sp_session`, refresh em `sp_refresh`, CSRF em `sp_csrf` e expiração em `sp_session_exp`.
4. A política de senha vem do backend. O front usa os limites e códigos para requisitos e força,
   sem duplicar a regra de validade.
5. O token de verificação e reset é lido da URL, removido com `router.replace` antes da chamada,
   e as páginas enviam `Referrer-Policy: no-referrer`.
6. A interface nova fica nas mesmas rotas públicas do login e não altera o header, a landing nem
   o app logado.

## Consequências

- Deploy sem SMTP mantém a tela anterior e evita cadastros que não conseguem verificar e-mail.
- O navegador nunca vê access ou refresh token.
- Mudanças na política de senha no servidor aparecem no front sem novo deploy.
