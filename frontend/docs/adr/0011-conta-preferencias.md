# ADR 0011: Preferências da conta em cookies e limites de privacidade

- Status: aceito
- Data: 2026-11-16
- Fase: F10

## Contexto

O contrato oferece apenas `GET /users/me` e `POST /auth/logout`. Não há edição de nome,
preferências da conta, organização, sessões, uso, exportação ou exclusão. O único caminho
para alterar `preferred_locale` no backend é `PUT /notification-preferences`, que substitui
os três canais de notificação e exige destino completo para SMS e WhatsApp. Usar esse PUT
para trocar o idioma poderia desabilitar canais ou exigir que o usuário redigitasse o
telefone, então ele não serve como preferência de conta.

O produto já persiste idioma e tema em cookies (`locale` e `theme`). A F10 acrescenta o
formato de data e precisa explicar por que ele também fica no navegador.

## Decisão

### Preferências no navegador

- Idioma continua no cookie `locale`, tema no cookie `theme` e o novo formato de data no
  cookie `date_format`.
- O `I18nProvider` recebe o formato inicial do servidor, aplica no `formatDate` quando a
  chamada usa `dateStyle` e expõe `setDateFormat` para atualização imediata.
- O formato `auto` preserva o comportamento anterior e usa o locale da interface. Os
  formatos explícitos `dmy`, `mdy` e `iso` substituem a ordem de data em chamadas com
  `dateStyle`, preservando hora e fuso quando existirem.
- O idioma continua chamando `router.refresh()` para atualizar server components. Tema e
  formato de data atualizam o estado e o cookie imediatamente, sem refresh.
- Nenhuma preferência é enviada ao backend, porque não existe endpoint dedicado. A lacuna
  e a proposta de `GET/PATCH /users/me/preferences` ficam em `BACKEND_GAPS.md`.
- Como não existe mutação de conta no contrato, não há atualização otimista de servidor a
  reverter. As preferências mudam no cliente e nos cookies. O diálogo de exclusão valida a
  confirmação e encaminha ao canal de privacidade; nenhuma chamada destrutiva é simulada.

### Perfil e organização somente leitura

- Nome, e-mail, avatar de iniciais e papel vêm de `GET /users/me`.
- Nome e e-mail são somente leitura porque não existe PATCH. A foto do Google não é
  exposta pela API e o avatar visual usa as iniciais reais.
- Organização, plano e membros não existem no backend. A tela mostra o papel real da conta
  e estados indisponíveis, sem inventar uma organização pessoal.

### Sessões e privacidade

- A expiração da sessão atual vem do cookie BFF `sp_session_exp` quando presente. O início
  da sessão não é exposto e aparece como indisponível.
- O logout atual usa o hook existente de F03. Logout global, lista de sessões, uso de
  armazenamento, exportação e exclusão não existem e ficam documentados.
- O canal de privacidade vem de `NEXT_PUBLIC_PRIVACY_CONTACT_URL` ou
  `NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL`, com fallback para `/suporte`.

### Exclusão de conta

- Não há `DELETE /account`. O fluxo de perigo usa um diálogo com `react-hook-form` e Zod
  que exige a palavra traduzida de confirmação e, ao validar, encaminha para o canal de
  privacidade. Nada é excluído automaticamente e a tela diz isso.
- O diálogo usa foco gerenciado pelo Radix Dialog e um `beforeunload` enquanto a
  confirmação digitada não foi enviada. Nenhum endpoint falso é chamado.

## Consequências

- As preferências sobrevivem a recarregamentos e ao logout no mesmo navegador, mas não
  acompanham a conta em outro dispositivo até o backend oferecer preferências de conta.
- O formato de data afeta apenas chamadas que usam `dateStyle`; rótulos customizados de
  linha do tempo e formatos relativos continuam próprios.
- A página de conta é honesta sobre o que não existe e não cria dados de organização,
  sessão, uso ou exclusão.
