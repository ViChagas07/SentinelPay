# ADR 0029: vinculação entre conta Google e conta por senha

- Status: aceito
- Data: 2026-11-23
- Fase: P20

## Contexto

O login por senha passa a criar contas com e-mail. O Google OIDC já cria contas por `google_sub`
e atualiza e-mail e nome. Um mesmo e-mail pode existir nos dois caminhos, e a vinculação
automática abre espaço para pré-sequestro de conta: alguém cadastra o e-mail de outra pessoa,
deixa a conta não verificada e o dono real entra pelo Google depois, herdando a conta plantada.

## Decisão

1. Se o cadastro por senha encontra e-mail existente, não cria conta, não altera a existente e
   responde de forma neutra. O dono recebe um e-mail informando a tentativa, com caminho para
   entrar ou recuperar a senha.
2. Se o login Google encontra conta por senha com o mesmo e-mail:
   - vincula `google_sub` somente quando `email_verified_at` local está preenchido e a identidade
     Google tem `email_verified=true`;
   - se a conta local não está verificada, não vincula e responde com erro genérico de OIDC,
     registrando `google_link_blocked` em `auth_events` sem revelar o motivo ao navegador.
3. Se o login Google encontra conta já vinculada por `google_sub`, mantém o comportamento atual.
4. Se o e-mail do Google divergir do e-mail local de uma conta vinculada, o perfil é atualizado
   como hoje, sem trocar `google_sub`, papel ou senha.
5. Uma conta pode ter senha, Google ou ambos; `auth_events` registra `google_linked`.

## Alternativas descartadas

- Vincular sempre pelo e-mail: permite pré-sequestro e troca silenciosa de identidade.
- Criar conta duplicada com mesmo e-mail: quebra unicidade e confunde recuperação.
- Bloquear qualquer vínculo: força usuários legítimos a manter duas contas.

## Consequências

- Contas por senha não verificadas não podem ser assumidas por um Google de terceiro.
- A vinculação exige que o usuário verifique o e-mail primeiro, com custo pequeno de UX.
- A política final de vinculação precisa de revisão jurídica e de produto.
