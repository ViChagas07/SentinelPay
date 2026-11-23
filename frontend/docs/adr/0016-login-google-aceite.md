# ADR 0016: login só com Google, abas ligadas ao OIDC e retorno por histórico

- Status: aceito
- Data: 2026-11-23
- Fase: F15

## Contexto

O painel direito de `/login` repetia o título e a descrição do painel esquerdo, não tinha
estrutura de formulário e oferecia um único botão sem contexto de aceite. A tarefa pedia abas
"Entrar" e "Criar conta", campos de e-mail e senha, recuperação de senha e verificação de e-mail.

O backend só oferece Google OIDC com Authlib e sessão JWT no BFF. O modelo de usuário não tem
senha, não há rota de cadastro, de recuperação ou de verificação de e-mail. Criar esses campos
seria interface sem função real.

## Decisões

1. Renderizar somente o que existe: Google como ação principal, abas com o mesmo fluxo real,
   aceite obrigatório, avisos do OIDC e selo de confiança. Nenhum campo ou link de e-mail e senha.
2. As abas "Entrar" e "Criar conta" existem porque o OIDC cobre os dois casos: o primeiro acesso
   cria a conta por `upsert` de `google_sub`. Não é simulação, é o mesmo endpoint com textos
   diferentes.
3. A aba ativa vive em `?modo=cadastro`, sincronizada com `router.push` e `scroll: false`. Isso
   permite compartilhar o link, usar o botão de voltar do navegador e manter o estado do aceite,
   porque a troca de aba não remonta a página.
4. O aceite é um checkbox compartilhado entre as abas, não um aviso de texto solto. O botão do
   Google usa `aria-disabled` em vez de `disabled` nativo, para permanecer focável com teclado e
   permitir anunciar o erro de aceite em vez de sumir do fluxo.
5. O retorno usa `router.back()` com detecção de `popstate`. Sem histórico interno, a navegação
   cai em `/` com `router.replace`, então o usuário nunca fica preso em um link que não volta.
6. O selo de confiança só aparece em HTTPS, consultado por `useSyncExternalStore` para não
   divergir entre servidor e cliente. O texto descreve apenas o que existe: conexão segura e
   processamento com criptografia (bucket privado com SSE AES256).
7. O logo do painel esquerdo cresce para 44 px de ícone com wordmark proporcional, via prop
   `size` no `Wordmark`. Nenhum asset é recriado.
8. O painel do formulário tem altura mínima de 28 rem. Como a aba "Cadastro" tem apenas um botão
   e um aviso, isso evita salto de layout na troca, sem criar altura artificial perceptível.
9. As lacunas de backend ficam na seção 23 de `BACKEND_GAPS.md`, com contrato proposto para
   cadastro, login, recuperação e verificação por e-mail.

## Consequências

- A tela volta a ser honesta: tudo que aparece funciona e nada simula autenticação.
- Habilitar e-mail e senha no futuro exige endpoints no backend e uma nova fatia de UI com os
  campos, a força de senha e as validações do servidor.
- O botão de voltar cobre o caso de link direto sem histórico, sem depender de `document.referrer`.
