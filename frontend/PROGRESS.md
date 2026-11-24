# PROGRESS do front-end

## Estado atual

- Fase atual: F20 (fallback de capacidades de autenticação) concluída.
- Próxima fase: nenhuma prevista. O front-end está em estado de entrega.
- Login: painel esquerdo preservado, com logo dobrado para 44 px e botão "Voltar" acima dele. Painel direito com abas Entrar e Criar conta. A aba Entrar mostra e-mail, senha e botão primário sempre que `password_enabled` está ligado, sem exigir SMTP. A aba Criar conta, a verificação e a recuperação dependem de `signup_enabled`, que exige provedor de e-mail. Aceite obrigatório, estado na URL por `?modo=cadastro` e selo de confiança em HTTPS.
- Landing: header com navegação centralizada, painéis do "Como funciona" trocando por segmento, régua do índice de risco colorida por faixa, seção de normas com respiro e CTA final centralizado e ampliado.
- Marca: símbolo oficial aplicado no header, sidebar, login, landing, carregamento, progresso, erro, vazio, rodapé e README. Originais em `assets/brand/originals/` e derivados em `public/brand/`.
- Acessibilidade: matriz axe em 16 rotas, 2 temas e 3 idiomas, com zero violações.
- Responsivo: 16 rotas em 360, 768, 1280 e 1920 px, sem rolagem horizontal; régua de risco completa no painel e no dossiê.
- i18n: dicionários completos em pt, es e en; texto fixo em JSX barrado no build.
- Sem mocks: varredura de produção zerada para mock, fixture, faker, lorem e nomes do protótipo.
- Sem travessão longo em `frontend/`; varredura incluída em `npm run check`.
- Favicon e ícones gerados do símbolo transparente, com manifest, `icon.svg` próprio, `apple-icon` sólido, Open Graph 1200x630 e metadados de ícones. O arquivo `SentinelPay_Favicon__2_.png` recebido é RGB com xadrez gravado e não é usado.
- Segurança: CSP e cabeçalhos, cookies HttpOnly e Secure, 401/403/429 tratados, `npm audit` sem crítica.
- Desempenho: Lighthouse 97/100/96 na landing na F13; painel com 93/100/96 na F11 e medição da F13 bloqueada pelo seed da F12. Visualizador e gráficos sob demanda.
- Entrega: Vercel documentada, README atualizado, relatório em `docs/QUALITY.md`.
- `/account` reúne perfil, organização, preferências, atalho de notificações, segurança, privacidade e zona de perigo com navegação lateral no desktop e abas roláveis no mobile.
- Idioma, tema e formato de data aplicam imediatamente e persistem em cookies. Perfil, organização, sessões e dados mostram somente o que a API expõe, com lacunas explícitas.
- `/pagamentos` lista os payables reais, mostra resumo e linha do tempo dos próximos vencimentos, permite confirmar, pagar e ajustar vencimento, envia recibo para análise e salva lembretes globais.
- `/notificacoes` lista alertas com cursor, filtro de tipo e leitura, marca lidas com atualização otimista, mantém o badge da sidebar coerente e persiste as preferências de canal.
- `/inteligencia` mostra um estado "Em desenvolvimento" honesto, sem métricas ou gráficos inventados, até existir endpoint de regras, casos e modelos.
- `/boletos` e `/folha` listam as análises por classe, com contagens, filtros, ordenação, paginação e estado na URL.
- As listas usam a amostra real de até 500 análises obtida por cursor, porque a API ainda não oferece filtros, totais nem os campos extraídos. A interface explica a limitação e mostra "+" quando a amostra é truncada.
- `/verificacao` e `/verificacao/nova` enviam PDF ou imagem, criam o job e acompanham o pipeline por SSE, com fallback automático para polling.
- `/verificacao/[id]` mostra o dossiê com score, classe, justificativa, evidências, campos, metadados e avisos honestos.
- A barra de progresso usa percentual, etapa e detalhe persistidos pelo backend, com subprogresso de OCR por página, estado indeterminado dentro de RAG e LLM e lista de sete etapas.
- O botão "Cancelar análise" aparece durante todo o job, pede confirmação, mostra "Cancelando..." e retorna para o envio após o cancelamento.
- Painel da F06, landing da F05, shell da F04, sessão da F03 e design system da F02 preservados.
- O backend foi alterado nesta fase por pedido explícito do usuário: progresso, SSE, cancelamento, migration e testes. Score, classes, prompts, RAG, thresholds e schema de resultado continuam intocados.

## Comandos de checagem

- `npm run check`: lint, typecheck, testes unitários, portões de conteúdo e build de produção.
- `npm run check:content`: i18n, dados fictícios, travessão longo e padrões inseguros.
- `npm run test:e2e`: Playwright em Chromium, porta 3100. Padrão de 1 worker e 1 retry local por causa do backend de testes compartilhado. Use `PLAYWRIGHT_WORKERS` para aumentar.
- `npm run test:a11y`: matriz axe, responsivo e cabeçalhos de segurança.
- `npm run test:a11y:report`: grava `docs/quality/axe-matrix.json`.
- `npm run analyze`: mede o bundle e falha acima de 280 kB de JS gzip por rota.
- `npm run lighthouse`: mede landing e painel contra build de produção.
- `npm run audit`: `npm audit --audit-level=critical`.
- `npm run format:check`: verificação do Prettier.
- `npm run api:types`: gera tipos do OpenAPI quando a API está no ar.

Resultados reais em 2026-11-16 (F11):

- `npm run check`: verde. ESLint e `tsc --noEmit` sem erros, testes unitários passando, portões de conteúdo zerados e build de produção concluído.
- `npm run test:e2e`: 158 testes na execução completa, 157 verdes e 1 retry transitório no cartão de suporte do shell, sem falha final. A suíte de teclado foi ampliada para as 16 rotas e validada em execução dedicada, com 8 casos adicionais.
- `npm run test:a11y`: verde, incluindo 96 análises axe, 64 combinações responsivas e os testes de cabeçalhos e cookies.
- `npm run analyze`: maior rota em 258,3 kB de JS gzip, abaixo do orçamento de 280 kB.
- `npm run lighthouse`: landing 99/100/96 e painel 93/100/96 (desempenho, acessibilidade, boas práticas).
- `npm run audit`: 0 críticas e 0 altas; 7 moderadas transitivas de desenvolvimento.

Resultados reais em 2026-11-17 (F12):

- `npm run lint`, `npm run typecheck`, `npm run test` (244 testes), `npm run check:content` e `npm run build`: verdes.
- Backend: `make check` com 906 testes sem Docker, 2 skips, cobertura 81,54%; `mypy` 405 arquivos; Ruff, format e import-linter verdes.
- Playwright: `e2e/verification.spec.ts` com 2 testes verdes (progresso real, retomada após reload e cancelamento) e `e2e/verification-errors.spec.ts` com 12 testes verdes. O painel de progresso passou no axe sem violações.
- Migration `0011_analysis_progress` aplicada após backup. Testes Docker de corrida de cancelamento verdes.
- Teste manual com API e worker reais: SSE entregou snapshot em `queued` e `running`, cancelamento em OCR retornou 202 `cancelling` e o estado final ficou `cancelled`, com score, relatório S3 e resultado parcial limpos.

## Feito em F20

- Correção: `/login` mostrado apenas com Google em produção mesmo após o deploy da F19.
- Causa: `fetchAuthCapabilities` devolvia `passwordEnabled: false` quando `/api/v1/auth/capabilities` falhava, embora o backend declare `auth_password_enabled = True`. O Render de produção não responde (DNS resolve, HTTP expira em 120 s), então o fallback desligava o formulário. Além disso, `LoginView` exige `passwordEnabled && policy !== null`, e o fallback nunca trazia a política.
- Correção em `lib/auth/capabilities.ts`: fallback explícito em três estados. `AUTH_PASSWORD_ENABLED=false` desliga entrada e cadastro; vazio mantém a entrada com `FALLBACK_POLICY` e cadastro desligado; `true` mantém entrada e cadastro para teste e desenvolvimento. A mesma regra vale para resposta HTTP não ok, JSON malformado e falha de rede.
- `signupEnabled` e `passwordResetEnabled` deixaram de herdar `passwordEnabled` quando o payload não traz os campos: agora o padrão é `false`, como no backend sem provedor de e-mail.
- Restaurado `target="_blank"` e `rel="noreferrer"` nos links de Termos e Privacidade do aceite, perdidos na reescrita da F19, para o checkbox não perder o estado.
- `frontend/.env.example` documenta o fallback de `AUTH_PASSWORD_ENABLED`.
- Verificação: com `API_INTERNAL_URL` em porta morta, o HTML de `/login` traz "passwordEnabled":true com os campos E-mail e Senha. 301 testes unitários, `e2e/login.spec.ts` (14 casos) e `e2e/legal.spec.ts` (3 casos) verdes.

## Feito em F19

- Diagnóstico: o formulário de senha existia, mas ficava oculto porque `password_enabled` dependia de provedor de e-mail. Por isso a tela mostrava só o Google.
- Backend: `AUTH_PASSWORD_ENABLED` passou a ser ligada por padrão e as capacidades foram separadas em `password_enabled` (login), `signup_enabled` (cadastro) e `password_reset_enabled` (recuperação). Login por senha não exige SMTP; cadastro e recuperação exigem.
- Compose e `.env.example` receberam as variáveis `AUTH_*` com padrão ligado e SMTP apontando para o Mailpit local.
- Front: painel direito reordenado conforme a referência, com abas, aceite, botão Google, divisor "ou", campos e botão primário. A aba Criar conta só aparece com `signup_enabled`, e o link "Esqueceu a senha?" só com `password_reset_enabled`.
- O envio não é mais bloqueado por `aria-disabled`: clicar sem o aceite mostra o erro acessível e foca o checkbox, e o botão permanece legível e operável por teclado. O estado desabilitado do botão primário passou a manter contraste AA.
- Validação real no navegador em 1440x950, temas escuro e claro, abas Entrar e Criar conta, com backend de auth respondendo pelas capacidades.

## Feito em F18

- Spec em `docs/specs/F16.md` e ADR em `docs/adr/0017-autenticacao-email-senha-bff.md`.
- Backend da P20 entregou `/auth/capabilities`, `/auth/password-policy`, `/auth/register`, `/auth/login`, `/auth/verify-email`, `/auth/resend-verification`, `/auth/forgot-password`, `/auth/reset-password` e `/auth/change-password`. O login por senha emite o mesmo par de cookies do Google e o BFF nunca devolve token ao JavaScript.
- BFF com `lib/session/password-auth.ts`, validação de origem, repasse de `Retry-After` e cookies, e Route Handlers em `/api/v1/auth/*`.
- `lib/auth` concentra capacidades com fallback desligado, política vinda do servidor, validação Zod, força de senha apenas visual, cliente de requisições e mapeamento de códigos de erro.
- `/login` renderiza o formulário de e-mail e senha somente com `password_enabled` ligado: e-mail, senha com mostrar e ocultar, "Esqueceu a senha?", botão primário, divisor "ou", nome completo, confirmar senha com validação em tempo real e requisitos reais da política. Com a flag desligada, a tela continua exatamente como antes, só com Google.
- Estados tratados: erro genérico de credenciais, 429 com tempo de espera, conta não verificada com reenvio, política de senha, erro de rede e sucesso com o mesmo redirecionamento pós-login.
- Telas novas `/verificar-email`, `/confirmar-email`, `/esqueci-senha` e `/redefinir-senha`, com `Referrer-Policy` no-referrer, remoção do token da URL antes da chamada, cooldown de reenvio e o mesmo design do login.
- Termos e Privacidade em pt, es e en atualizados para e-mail e senha, tokens, eventos de segurança, consentimentos, provedor de e-mail e exclusão de conta. `LEGAL_VERSION` passou para 1.1.
- Testes: 6 arquivos novos em `lib/auth` e componentes, 13 e2e em `e2e/password-auth.spec.ts` e 14 em `e2e/login.spec.ts`, incluindo axe nas duas abas e nos dois temas.

## Resultados reais em 2026-11-23 (F18)

- `npx tsc --noEmit`, `npx eslint .`, `npx vitest run` (298 testes), `npm run check:content` e `npm run build`: verdes.
- `e2e/login.spec.ts` com 14 testes e `e2e/password-auth.spec.ts` com 13: verdes.
- Backend: `ruff`, `mypy`, `lint-imports` e `pytest` completos verdes, com os testes novos de política, serviço e rotas.

## Feito em F12

- Spec em `docs/specs/F12.md` e ADR em `docs/adr/0013-progresso-sse-cancelamento.md`.
- Schemas Zod aceitam `running`, `cancelling` e `cancelled`, além de `progress` com etapa, percentual, detalhe, início e estado indeterminado.
- Cliente SSE em `lib/verification/events.ts`, com parser testado, reconexão própria e queda automática para polling após duas falhas.
- O snapshot inicial do SSE é aplicado no cache do TanStack Query; abrir a tela no meio da análise mostra o estado persistido sem depender de estado local.
- `useAnalysisJob` liga e desliga o SSE conforme o status terminal, e `useCancelAnalysis` chama `POST /analyses/{id}/cancel` com validação Zod.
- Painel refeito com barra determinate, `role="progressbar"`, `aria-valuenow`, `aria-live` no texto da etapa, percentual e lista de sete etapas.
- OCR mostra "Página N de M"; RAG e LLM mostram estado indeterminado dentro da etapa, sem barra parada sem texto.
- Avisos de conexão perdida, reconexão e fallback de polling, além de estados de cancelado, erro, resultado indisponível e concluído com transição suave.
- Botão "Cancelar análise" com diálogo de confirmação, estado "Cancelando...", retorno ao envio e tratamento de 409.
- Fluxos de boleto, folha, Central de Verificação e recibo usam o mesmo painel; o dossiê de recibo também acompanha e cancela a análise.
- Testes novos para progresso, parser SSE, fallback de polling e confirmação de cancelamento. 244 testes unitários verdes.

## Feito em F17

- Spec em `docs/specs/F17.md` e ADR em `docs/adr/0015-paginas-legais.md`.
- Conteúdo jurídico em `lib/legal/content/{pt,es,en}.ts`, estrutura tipada em `types.ts` e versão única em `lib/legal/version.ts` (`LEGAL_VERSION` 1.0, `LEGAL_UPDATED_AT` 2026-11-23).
- Política com 15 seções e Termos com 12, em pt, es e en, com aviso de prevalência do português fora do pt.
- `lib/legal/identity.ts` lê `NEXT_PUBLIC_LEGAL_*` e omite campo ausente, sem placeholder. Testado.
- Componentes `features/legal/components/legal-document.tsx`, `legal-blocks.tsx` e `legal-toc.tsx`: sumário sticky no desktop e recolhível no mobile, destaque da seção visível por IntersectionObserver, âncoras copiáveis, tabelas com rolagem horizontal, botão "Voltar ao topo" e links cruzados com `/account`.
- Estilo de impressão em `styles/globals.css` para `@media print`, com fundo branco e texto preto.
- Os links de `/termos` e `/privacidade` no aceite do login abrem em nova aba, preservando o checkbox marcado.
- Testes Vitest `lib/legal/content/content.test.ts` (paridade de seções e âncoras entre idiomas, tabelas bem formadas, sem travessão longo) e `lib/legal/identity.test.ts`. Playwright `e2e/legal.spec.ts` com 3 casos.
- `/termos` e `/privacidade` continuam nas mesmas rotas. Nenhum endpoint, migration, tabela ou alteração de autenticação.

### Fase 0: inventário factual que sustenta o texto

- Login: Google OIDC com escopos `openid email profile`. Persistimos `google_sub`, `email`, `name`, `preferred_locale`, `timezone` e `role`. A foto do perfil não é armazenada; o shell usa iniciais.
- Documentos: upload multipart com PDF, PNG e JPG, até 25 MB (`UPLOAD_MAX_MB=25`), 50 páginas no PDF (`PDF_MAX_PAGES=50`) e 20 páginas de OCR (`OCR_MAX_PAGES=20`). PDF criptografado é recusado. Guardamos `s3_key`, `sha256`, tamanho, `content_type`, nome sanitizado e tipo. O texto do OCR não é persistido.
- Resultado: `score` 0 a 100, `band` (`low`, `attention`, `high`), evidências por regra, justificativa, campos extraídos (linha, código de barras, valor, vencimento, beneficiário, pagador, banco, empregador, competência, itens, líquido, IRRF, dependentes, emissor, referência), versões de regra, modelo e prompt, além de `degradation_flags`. CPF e CNPJ saem mascarados no relatório.
- Armazenamento: PostgreSQL e Redis na Railway (`postgres.railway.internal`); arquivos e relatórios em bucket S3 privado na região `us-east-2` com SSE AES-256; traces no Langfuse em `us.cloud.langfuse.com` quando habilitado; front-end na Vercel.
- IA: regras determinísticas, classificador estatístico treinado com dados 100% sintéticos e modelo de linguagem via endpoint compatível com OpenAI, configurado para LM Studio local (`LLM_BASE_URL`). O trecho enviado ao LLM é mascarado (CPF, CNPJ, nomes, valores, e-mail, telefone, endereço, chave Pix, sequência longa de dígitos) e limitado a 6.000 caracteres. Não há treinamento com dados de usuário.
- Observabilidade: Langfuse com `ObservabilityMasker` aplicado como `mask` do cliente, hash de identificadores e remoção de PII; OpenTelemetry com coletor local e Prometheus; logs com `PIIMaskingFilter`. O Sentry do front-end só é carregado com DSN e envia eventos sem cookies, cabeçalhos ou dados pessoais.
- Notificações: e-mail por SMTP. SMS e WhatsApp têm preferência, consentimento e destino cifrado em AES-GCM, mas os adaptadores são apenas de console, sem provedor externo integrado. A política diz isso de forma explícita.
- Cookies: `sp_session`, `sp_session_exp`, `sp_refresh`, `sp_csrf`, `sp_oidc`, `refresh_token`, `csrf_token`, `theme`, `locale`, `date_format` e `sp_sidebar`. Sem localStorage, sessionStorage, analytics ou rastreadores de terceiros.
- Retenção e exclusão: não há expurgo automático de documentos e análises nem `DELETE` de conta, documentos ou análises. Cancelar remove o relatório parcial. A política descreve esse comportamento real e remete ao canal de privacidade.
- Segurança: HTTPS com HSTS, CSP, cookies HttpOnly, SameSite=Lax e Secure, rotação de refresh token com detecção de reuso, CSRF nas rotas autenticadas, rate limit Token Bucket em Redis por IP e por usuário (429 com `Retry-After`), verificação de tipo real, tamanho e páginas, SSE AES-256 no S3, AES-GCM nos destinos de notificação, mascaramento em logs e traces e guardrails de prompt. Sem certificação declarada.

## Resultados reais em 2026-11-23 (F17)

- `npm run lint`, `npm run typecheck`, `npm run test` (266 testes), `npm run check:content` e `npm run build`: verdes.
- `e2e/legal.spec.ts`: 3 testes verdes. `axe matrix`, `responsivo` e `teclado` para `/termos` e `/privacidade`: verdes.
- Verificação visual em 1440x900 e 390x844, nos temas claro e escuro, em pt e en, além de `emulateMedia` de impressão com fundo branco e texto preto.

## Feito em F15

- Spec em `docs/specs/F15.md` e ADR em `docs/adr/0016-login-google-aceite.md`.
- Diagnóstico: o backend só tem Google OIDC (Authlib) com JWT de sessão no BFF, e o modelo `users` não tem senha. Não existe cadastro, login, recuperação nem verificação por e-mail e senha, então nada disso foi renderizado e o contrato desejado ficou na seção 23 de `docs/BACKEND_GAPS.md`.
- Painel esquerdo preservado. O logo passou de 28 px para 44 px de ícone, com wordmark proporcional via prop `size` no `Wordmark`, usando os assets atuais sem recriar.
- Botão "Voltar" em ghost com `ArrowLeft` e `ArrowUp` acima do logo no desktop e no topo do cabeçalho no mobile. Usa `router.back()` e cai em `/` com `router.replace` quando não há histórico, detectado pelo `history.length` e por um `popstate` em 500 ms.
- Painel direito refeito: sem losango solto e sem repetição de título. Agora tem abas Entrar e Criar conta (`role=tablist`, setas, Home e End, estado em `?modo=cadastro`), título e subtítulo próprios por aba, checkbox de aceite com links reais para `/termos` e `/privacidade`, botão do Google com ícone oficial, estado de carregamento e `aria-busy`, rodapé de alternância e selo de confiança apenas em contexto HTTPS.
- O botão do Google usa `aria-disabled` e continua focável, para anunciar o erro de aceite com `role="alert"`, `aria-invalid` e `aria-describedby` em vez de sumir do fluxo de teclado.
- Logo oficial do Google em SVG local (`components/brand/google-icon.tsx`), sem requisição externa, compatível com a CSP.
- Entrada do formulário e troca de aba com fade e translate por CSS, desligados em `prefers-reduced-motion`. Altura mínima de 28 rem no painel evita salto de layout.
- i18n em pt, es e en para abas, títulos, subtítulos, aviso de primeiro acesso, rodapés, aceite, erro de aceite, voltar e selo.
- Testes: `lib/auth/login-mode.test.ts` e `lib/session/back-navigation.test.ts` novos. `e2e/login.spec.ts` cresceu para 12 casos, incluindo axe nas duas abas e dois temas, bloqueio sem aceite, troca por clique e por seta com URL, ausência de campos de e-mail e senha e o botão de voltar.

## Resultados reais em 2026-11-23 (F15)

- `npx tsc --noEmit`, `npx eslint .`, `npx vitest run` (253 testes) e `npm run check:content`: verdes.
- `e2e/login.spec.ts`: 12 testes verdes. `e2e/a11y-matrix.spec.ts`, `e2e/responsive.spec.ts` e `e2e/keyboard.spec.ts` para `/login`: verdes.
- Verificação visual em 1440x900, 1440x740 e 390x844, nos temas claro e escuro, nas abas Entrar e Criar conta, sem erro de console e sem divergência de hidratação.

## Feito em F14

- Spec em `docs/specs/F14.md`.
- Causa raiz dos defeitos visuais: a regra `turbopack.rules` do `next.config.ts` aplicava `@tailwindcss/turbopack` a todo `*.css`, então o `landing.module.css` perdia as classes de módulo e as mesmas chegavam como `undefined`. A regra foi reduzida a `styles/globals.css`, com verificação no DOM.
- Header público em grid de três colunas iguais a partir de `lg`, com navegação centralizada e ações alinhadas à direita. Abaixo de `lg` o menu mobile continua igual.
- Itens de tema e idioma no dropdown recebem `gap-3` e ícones de 16 px com `shrink-0`, separando ícone e rótulo.
- "Como funciona" sem `items-start` no grid: a coluna do painel passa a acompanhar a altura dos três segmentos e o `sticky` funciona. Cada segmento tem borda esquerda petróleo quando ativo, com `min-h-[62vh]` para dar ritmo de rolagem, e o painel troca entre envio, análise e decisão.
- Ýndice de risco: track nativo transparente, trilho próprio de ponta a ponta com preenchimento proporcional e marcadores de 40 e 70. A cor segue a faixa: azul de demonstração em baixo, amarelo em médio e vermelho em alto, aplicada ao preenchimento, ao polegar e ao selo de classe em destaque.
- Paleta de demonstração em `getLandingRiskPalette` com teste próprio; o restante do app continua com `--risk-low`, `--risk-medium` e `--risk-high`.
- Normas: o primeiro item deixa de usar `first:pt-0` e todos os itens seguem com `py-9` e número alinhado à primeira linha do título.
- CTA final centralizado nas duas colunas, com 4 rem de altura, texto maior e fundo verde musgo próprio (`--landing-cta` em `#2e6b50`, hover `#377a5c`), com borda petróleo e texto `--on-petrol`.
- Contraste do itálico da landing: novo token `--landing-accent` em `#3f8272`, que passa de 2,98:1 para acima de 3:1 sobre `--landing` e mantém `light-dark` para o tema escuro.
- Dropdowns de tema e idioma com `sideOffset={10}`, separando o menu do botão que o abre.

## Resultados reais em 2026-11-23 (F14)

- `npm run lint`, `npm run typecheck`, `npm run test` (245 testes), `npm run check:content` e `npm run build`: verdes.
- `e2e/landing-accessibility.spec.ts`: 6 testes verdes (2 temas e 3 idiomas), após ajustar o itálico e trocar o destaque de segmento por borda em vez de opacidade.
- `e2e/landing.spec.ts`, `e2e/responsive.spec.ts`, `e2e/a11y-matrix.spec.ts` e `e2e/keyboard.spec.ts`: 59 testes verdes.
- Baselines de `landing-light` e `landing-dark` regravados. As baselines do painel falham neste ambiente mesmo com o código de HEAD, por diferença de ambiente já registrada, e foram mantidas como estavam.
- Verificação visual em 1440x900 e 390x844, nos temas claro e escuro, incluindo o dropdown de tema, a régua nas três faixas e o CTA final.

## Resultados reais em 2026-11-17 (F13)
- `npm run check`: verde. ESLint, `tsc --noEmit`, 244 testes unitários, portões de conteúdo e build de produção.
- Lighthouse na landing: 97 de desempenho, 100 de acessibilidade e 96 de boas práticas, com LCP de 1,1 s, LCP observado de 177 ms e TBT de 180 ms. A primeira medição ficou baixa por concorrência com a suíte Vitest da F12; a medição final foi feita com a máquina ociosa.
- O painel não pôde ser remedido com a mesma base da F11: o script de seed da F12 cria uma análise com status `processing` e falha na constraint `ck_analyses_status` do backend. Uma medição avulsa com sessão sem dados semeados deu 73/100/96 e não é comparável. A lacuna está registrada em `docs/BACKEND_GAPS.md`.
- Verificação visual em 1440x900 e 390x844, nos temas claro e escuro: landing, login, painel, menu mobile, 404 e rodapé.
- Favicons validados em 16, 32, 48, 180, 192 e 512 px sobre fundo claro e escuro. O `apple-icon` foi conferido com fundo sólido.
- `npm run format:check`: pendente nos arquivos da F12 que não pertencem a esta fase; os arquivos da F13 foram formatados.

## Feito em F13

- Spec em `docs/specs/F13.md` e ADR em `docs/adr/0014-identidade-visual.md`.
- Auditoria inicial: o app usava um SVG desenhado à mão que não era o símbolo oficial, favicons aproximados, nenhum manifest e nenhum `next/image` para a marca.
- Originais copiados sem recompressão para `assets/brand/originals/`, com SHA-256 conferido. O favicon recebido foi descartado por ser RGB sem alfa e ter xadrez nos pixels.
- Derivados recortados pelo bounding box de 745x748 px: símbolo em 512, 256, 128 e 64, fundo branco em 512 e 256 e variante clara em 512, 128 e 64.
- Variante compacta com o mesmo desenho e traços mais grossos para 28 a 64 px, porque o traço original de 6 px no losango desaparece no header. A versão original segue disponível para formatos grandes.
- Cores amostradas do original e registradas em `styles/tokens.css`: `--brand-frame: #2a716d`, `--brand-mark: #4d927f`, `--brand-frame-on-dark: #7bbcb0` e `--brand-mark-on-dark: #a7d2ca`. O original não foi recolorido.
- SVG reconstruído com a geometria medida no raster e comparado ao PNG por IoU de alfa de 0,848, sem distorção.
- Favicon próprio gerado do símbolo: `app/favicon.ico` com 16, 32 e 48, `app/icon.png` com 512, `app/apple-icon.png` com 180 e fundo petróleo, `public/icon-192.png`, `public/icon-512.png`, `public/icon.svg` e `public/favicon-alert.svg` redesenhado.
- `app/icon.svg` antigo removido. O alternador de alerta continua usando `/icon.svg` e `/favicon-alert.svg`.
- Metadata raiz com title, description, applicationName, manifest, icons, openGraph e twitter. Landing com imagem Open Graph declarada. `public/manifest.webmanifest` com name, short_name, theme_color, background_color e ícones 192 e 512.
- Open Graph 1200x630 gerado no App Router com o símbolo real em base64, fundo petróleo, nome da marca, tagline e eyebrow.
- Símbolo aplicado no header público, sidebar e header mobile do app, login, hero da landing, carregamento, barra de progresso, 404, 500, estados vazios, rodapés e README.
- Sidebar e login usam a variante clara em fundo petróleo. O logo do sidebar aponta para `/painel`; o teste e2e foi atualizado.
- `next/image` com largura, altura, `alt="SentinelPay"` e sem distorção. `priority` apenas no logo do header público e no logo da sidebar.
- Relatórios PDF e e-mails transacionais não existem no front. O asset com fundo branco fica em `public/brand/logo-symbol-on-white-512.png` e a integração foi registrada em `docs/BACKEND_GAPS.md`.

## Feito em F11

- Spec em `docs/specs/F11.md` e ADR em `docs/adr/0012-qualidade-seguranca-desempenho.md`.
- Portão `npm run check:content` com três scripts: paridade de i18n e texto JSX fixo, dados fictícios e travessão longo, e padrões inseguros de código.
- Script de i18n com AST do TypeScript: compara chaves e placeholders entre pt, es e en, recusa locale extra e varre texto JSX e atributos textuais.
- Varredura de dados fictícios em código de produção, com testes e documentação fora do escopo. Varredura de travessão longo em código, testes e documentação.
- Cabeçalhos de segurança em `next.config.ts`: CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, COOP, CORP e HSTS em produção. `vercel.json` repete os cabeçalhos de borda.
- Cookies Secure também quando `x-forwarded-proto` indica HTTPS. Teste unitário cobre o cabeçalho e teste e2e cobre HttpOnly e SameSite.
- Interceptor de 429 com toast traduzido, respeito a `Retry-After` e retry único na consulta quando a espera é curta. 401 passou a navegar sem `router.refresh()` concorrente, que cancelava o redirecionamento.
- Observabilidade opcional por Sentry, com import dinâmico, coleta desligada, sanitização de PII, documento e query string, e testes unitários.
- Usuário inicial do shell buscado no servidor com timeout e fallback para o cliente. O título do painel passa a ser renderizado no HTML inicial.
- Transição de página sem opacidade inicial, reduzindo o LCP do painel de cerca de 4,8 s para menos de 1 s no laboratório.
- Visualizador de PDF e gráficos movidos para `next/dynamic` com skeleton acessível.
- Script `scripts/analyze-bundle.mjs` com orçamento de 280 kB de JS gzip e script `scripts/lighthouse.mjs` com sessão real e falha abaixo de 90.
- Suíte e2e nova: matriz axe em 16 rotas, 2 temas e 3 idiomas, teclado, responsivo em quatro larguras, régua de risco, cabeçalhos, cookies, 429, 401 e regressão visual nos dois temas.
- Correções de acessibilidade: ordem de títulos em `/servico-indisponivel` e nome acessível das verificações recentes.
- Relatório em `docs/QUALITY.md` com Lighthouse, axe, bundle, responsividade, segurança e auditoria.
- README com como rodar, testar, medir e implantar na Vercel.
- Nenhum arquivo fora de `frontend/` foi alterado. Backend, migrations, Compose, banco, infraestrutura e knowledge base permanecem intocados.
## Feito em F10

- Spec em `docs/specs/F10.md` e ADR em `docs/adr/0011-conta-preferencias.md`.
- Layout de conta com cabeçalho editorial, navegação lateral por sete seções e abas horizontais roláveis no mobile. A navegação usa `role="tablist"` com setas, Home e End, foco visível e painel único.
- Perfil real de `GET /users/me` com avatar de iniciais, nome e e-mail somente leitura, selo "Gerenciado pelo Google" e explicação de que a API não permite editar nome nem expõe a foto.
- Organização com papel real da conta e estados "Não disponível" para nome, plano e membros, sem inventar uma organização pessoal.
- Preferências com `react-hook-form` e Zod para idioma, tema e formato de data. Idioma usa o cookie existente e atualiza o shell; tema e formato aplicam imediatamente. O formato de data foi integrado ao `formatDate` para chamadas com `dateStyle`, com exemplo ao vivo e persistência pelo cookie `date_format`.
- Atalho para os canais de alerta em `/notificacoes#canais` e para a central de notificações.
- Segurança com provedor Google, expiração real do cookie BFF quando disponível, início de sessão explicitamente indisponível, logout da sessão atual pelo hook existente e logout global desabilitado com explicação.
- Privacidade com documentos e armazenamento "Não informado pela API", exportação e exclusão encaminhadas ao canal configurado por `NEXT_PUBLIC_PRIVACY_CONTACT_URL` ou `NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL`, com fallback `/suporte`.
- Zona de perigo com diálogo que exige a palavra traduzida de confirmação, usa `react-hook-form` e Zod, nunca envia DELETE inexistente e encaminha ao canal de privacidade. Toast de erro na palavra errada e de confirmação validada, aviso de `beforeunload` enquanto a confirmação não foi enviada e retorno de foco ao botão ao fechar.
- Nova dependência de front-end: `react-hook-form` e `@hookform/resolvers`, usadas nas preferências e na confirmação de exclusão.
- Testes unitários de formato de data, contato de privacidade, schema de preferências, confirmação de exclusão e aviso de alterações não salvas.
- Testes e2e de perfil e estados honestos, persistência de idioma, tema e formato de data, confirmação de exclusão sem DELETE, logout da sessão atual, axe e mobile.
- Lacunas completas na seção 19 de `docs/BACKEND_GAPS.md`.

## Feito em F09

- Spec em `docs/specs/F09.md` e ADR em `docs/adr/0010-pagamentos-notificacoes-inteligencia.md`.
- Central de pagamentos com cabeçalho editorial, resumo de a vencer, vence hoje e em atraso, linha do tempo horizontal de 30 dias com marcações reais e lista ordenada por vencimento.
- A lista usa payables reais com amostra por cursor de até 500 itens, filtro de situação no servidor, paginação local de 10 itens, descrição, valor em BRL, vencimento, situação derivada de `status` e `due_date`, e ações.
- Confirmar vencimento, marcar como pago com diálogo de confirmação e ajustar vencimento com data validada. Excluir aparece desabilitado com a explicação de que a API não oferece DELETE. Nenhum dado fictício.
- Cadastro de recibo envia o arquivo real para `POST /analyses` com `kind=receipt`, valida com Zod as mensagens traduzidas, mostra emissor, valor e vencimento como extraídos após a análise e navega para o dossiê.
- Lembretes globais com antecedência, horário local e canal `in_app`, persistidos em `PUT /payables/reminder-preferences` com atualização otimista e reversão. E-mail, SMS e WhatsApp apontam para Notificações.
- Linha do tempo com scroll contido no próprio bloco, cards no mobile, rótulos relativos e link para o vencimento focado. Deep link `?vencimento=` destaca o payable e mostra aviso honesto se ele não estiver na amostra.
- Notificações com lista "Recentes" de lidas e não lidas, cursor com carregar mais, filtro de tipo e de não lidas no servidor, canal desabilitado e explicado, polling de 20 s e badge da sidebar usando a mesma consulta de não lidas.
- Marcar uma ou todas como lidas com atualização otimista, reversão em erro, atualização da lista e do contador. Cada item deriva o destino real do payload: análise no dossiê ou vencimento na central de pagamentos. Sem destino, não vira link.
- Painel de canais de alerta com E-mail, SMS e WhatsApp, interruptores acessíveis, destino mascarado, consentimento, validação E.164, reentrada obrigatória quando o destino está mascarado, atualização otimista e persistência comprovada após recarregar.
- Inteligência antifraude como estado "Em desenvolvimento" com título em serif, frase honesta, lista do que virá e botão para o painel. Nenhum número, gráfico, caso ou métrica fictícia.
- Testes unitários de situação de payable, resumo, linha do tempo, paginação, filtros, cursor, formulário de lembrete, alvos de notificação, canais, máscara de telefone, validação Zod de canais, atualização otimista e formulário de recibo.
- Testes e2e de payables e timeline, pagar, remarcar, exclusão indisponível, deep link, recibo real, lembretes persistidos, mobile, badge e lista de notificações, leitura, preferências persistidas, reversão otimista e inteligência sem dados.
- Lacunas completas na seção 18 de `docs/BACKEND_GAPS.md`.

## Feito em F08

- Spec em `docs/specs/F08.md` e ADR em `docs/adr/0009-listas-boletos-folha.md`.
- Cabeçalho numerado em serif, descrição curta e botão "Nova verificação" com o tipo já selecionado em `/verificacao?tipo=boleto` ou `?tipo=payslip`.
- Abas Todos, Baixo, Médio e Alto com contagens reais da amostra carregada da API. As contagens respeitam período, status e busca, não a aba ativa, e recebem "+" quando o cursor ainda tem páginas.
- Filtros de período, status do job, classe e busca por identificador, ordenação por data ou score em ordem crescente ou decrescente, e limpeza de todos os filtros.
- Faixa de valor, emissor/CNPJ e ordenação por valor aparecem desabilitados com explicação, porque a lista da API não devolve esses campos. A busca cobre o identificador da análise e a interface informa isso.
- Estado completo em query params (`band`, `status`, `period`, `q`, `sort`, `dir`, `page`), com restauração por recarga ou link, volta para a página 1 ao mudar filtro e ajuste de página fora do intervalo.
- Paginação de 10 itens por página. O transporte segue o cursor do contrato até 500 análises; a visão pagina essa amostra e explica a ausência de paginação filtrada no servidor.
- Tabela de boletos e de contracheques com DataTable no desktop e lista empilhada própria no mobile. A régua de risco completa fica visível no mobile, sem rolagem horizontal.
- Campos não devolvidos pela API (número do documento, beneficiário, CNPJ, valor, vencimento, empregador, competência e líquido) aparecem como "Indisponível", sem valor fictício.
- Linhas em análise mostram indicador discreto e a consulta atualiza sozinha com backoff de 2,5 s a 20 s, parando quando não há job ativo. Teste e2e confirma a troca de "Em análise" para "Analisado".
- Cada linha tem link para `/verificacao/[id]`; setas para cima e para baixo movem o foco entre as linhas visíveis e Enter abre o dossiê.
- Estados de carregamento com skeleton, vazio por filtro com "Limpar filtros", vazio total com convite à primeira verificação, erro com tentar novamente e amostra truncada com aviso honesto.
- Nenhum botão de exportar CSV ou excluir foi exibido porque as rotas não existem. As lacunas estão na seção 17 de `docs/BACKEND_GAPS.md`.
- Testes unitários de parsing e serialização da URL, agrupamento de status, período, busca, contagens, ordenação, paginação e coleta por cursor. Testes e2e de filtros, contagens, paginação, teclado, dossiê, polling, folha, axe, vazio, erro e mobile.
- Extensão apenas do suporte de testes `e2e/support/fake-backend.ts` para aceitar lista dinâmica. Nenhum dado de teste vazou para a interface.

## Feito em F07

- Spec em `docs/specs/F07.md` e ADR em `docs/adr/0008-verificacao.md`.
- Upload em `/verificacao` e `/verificacao/nova` com tipo obrigatório (Boleto ou Contracheque), arrastar e soltar, colar, seleção por teclado, validação de PDF/PNG/JPEG e limite espelhando o backend (`NEXT_PUBLIC_UPLOAD_MAX_MB`, 25 MiB).
- Envio por `XMLHttpRequest` com progresso real em bytes, cancelamento por `AbortController`, mensagens traduzidas para 413/422 e proteção contra duplo envio.
- Aviso de segurança baseado no backend real: sessão autenticada, bucket privado com SSE AES256 e acesso restrito ao dono.
- Pipeline com os cinco estágios documentados, estado do job pelos status reais, progresso indeterminado quando a API não informa etapa, tempo decorrido e backoff de polling.
- Pré-visualização local de PDF ou imagem com linha de leitura animada e respeito a `prefers-reduced-motion`.
- Dossiê em duas colunas com visualizador, RiskRuler grande, RiskStamp, justificativa em serif, evidências traduzidas, tabela de campos com estado vazio honesto, metadados, flags, ações e aviso permanente.
- Retomada do job ao recarregar por polling de `GET /api/v1/analyses/{id}` e lista de verificações recentes com estado real.
- Object URLs revogadas, nenhum documento em storage do navegador e nenhum conteúdo de documento no console.
- Lacunas registradas em `docs/BACKEND_GAPS.md`: limite de 300 MB pedido versus 25 MiB do backend, ausência de etapa, documento, campos, coordenadas, relatório, revisão, retry e filtros de lista.

## Feito em F06 (fase anterior)

- Spec em `docs/specs/F06.md` e ADR em `docs/adr/0007-dashboard.md`.
- Saudação com o nome real do usuário e a data atual no idioma da interface e no fuso do perfil, usando `Intl` e fallback para UTC quando o fuso é inválido.
- Faixa "Risco médio" com número grande em Instrument Serif, RiskRuler grande, média da amostra, variação em pontos contra o período anterior e frase de contexto calculada com os dados.
- Bloco "Documentos em conformidade" com rótulo, percentual e barra de progresso próprios. A proporção é análises de risco baixo sobre análises concluídas e nunca é colocada na régua de 0 a 100.
- Resumo do período em três linhas compactas com sparkline: documentos analisados, alertas de risco alto e comprovantes pendentes.
- Análises recentes em DataTable com ID em mono, tipo, emissor, CNPJ, valor, RiskRuler compacta, classe, data relativa e links para `/verificacao/[id]` e `/verificacao`.
- Emissor, CNPJ, valor e número do documento aparecem como "Indisponível" porque a lista da API não expõe esses campos. A lacuna está na seção 15 de `BACKEND_GAPS.md`.
- Distribuição de risco com StripChart, seletor de 7, 30 e 90 dias, dados reais da lista de análises e cores de risco apenas nos segmentos das faixas.
- Próximos vencimentos ordenados por data crescente, com rótulos relativos por fuso, valor em BRL, status e link para a Central de Pagamentos.
- Conta nova mostra o bloco em serif "Envie seu primeiro documento" com botão para `/verificacao`, sem métricas falsas.
- Estados de carregamento com shimmer, vazio por período, erro com tentar de novo e refetch ao voltar o foco nas consultas do painel.
- Título e favicon de alertas de risco alto continuam sendo atualizados pelo shell e foram cobertos por teste com duas notificações não lidas.
- O resumo é calculado sobre a lista de análises porque não existe endpoint de agregação. O painel pagina até 500 análises no período e mostra "Amostra parcial" quando o limite corta a janela. A nota fica visível e o gap está documentado.
- O contador de comprovantes pendentes usa a primeira página de payables ativos. Com `next_cursor` e contagem maior que zero, mostra "+". Sem certeza, mostra "Indisponível".
- A rota `/verificacao/[id]` recebeu um estado provisório honesto na F06 e foi substituída pelo dossiê real na F07.
- Testes unitários dos formatadores de data, fuso, vencimento, valores relativos, séries diárias, média, conformidade, contagem limitada e ordenação de payables.
- Testes e2e com seed de banco apenas no ambiente de teste, incluindo conta nova e conta com dados.

## Fases anteriores (concluídas)

- F09: Pagamentos, notificações e inteligência com dados reais e estados honestos.
- F08: Listas de boletos e folha com contagens, filtros na URL, polling e mobile.
- F07: Central de Verificação com upload, pipeline, dossiê e estados honestos.
- F06: Painel Principal com risco médio, conformidade, métricas, distribuição e vencimentos.
- F05: landing pública com i18n, temas, SEO, Open Graph e páginas legais.
- F04: shell autenticado com sidebar, header, navegação, atalhos, alertas e responsividade.
- F03: sessão BFF com cookies HttpOnly, login, logout e expiração.
- F02: design system e catálogo `/dev/design`.
- F01: fundação Next.js, tokens, i18n, cliente de API.
- F00: contrato e lacunas documentados.

## Bloqueios e riscos

- O backend limita o upload a 25 MiB (`UPLOAD_MAX_MB`), enquanto o pedido de produto falava em 300 MB. O cliente espelha o limite real e a divergência está na seção 16 de `BACKEND_GAPS.md`.
- O detalhe da análise não informa etapa, percentual, documento, campos extraídos, coordenadas, idioma, versão do pipeline, relatório para download nem revisão. A interface usa progresso indeterminado e estados vazios honestos.
- O progresso do XHR mede o envio até o BFF. A análise em si continua no worker e não expõe progresso de processamento.
- As rotas de retry e cancelamento não existem. "Tentar novamente" repete o polling; o reenvio cria um novo job quando o arquivo local ainda está em memória.
- Não existe endpoint de agregação. O painel da F06 continua calculando sobre a lista paginada, com "Amostra parcial" quando aplicável.
- A lista de análises não expõe número do documento, beneficiário, empregador, CNPJ, valor, vencimento, competência ou líquido. As tabelas do painel e das listas mostram "Indisponível".
- A API não aceita filtros, ordenação nem contagens e não devolve total. As listas da F08 usam até 500 análises reais por cursor, filtram e paginam essa amostra, mostram "+" quando truncada e registram a lacuna na seção 17 de `BACKEND_GAPS.md`.
- Exportação CSV e exclusão de documento não existem. Nenhum botão foi exibido; a proposta está na seção 17.
- Payables não separam emissor da descrição, não têm `GET /{id}`, `DELETE`, edição de valor ou descrição, criação manual, anexo opcional, lembrete por recibo nem total agregado. A F09 usa amostra por cursor de até 500, campos reais e estados honestos. As lacunas estão na seção 18 de `BACKEND_GAPS.md`.
- A API não tem SSE. Notificações usam polling de 20 s. O item não devolve canal de entrega, o filtro de canal fica desabilitado e as preferências não têm verificação de contato.
- O GET de preferências mascara SMS e WhatsApp, mas o PUT substitui os três canais e exige o número completo. A interface pede reentrada do número antes de salvar alterações quando um canal telefônico já está ativo.
- Não existe endpoint de inteligência antifraude. A rota mostra "Em desenvolvimento", sem números ou gráficos, e a seção 18 descreve o contrato necessário.
- Não existe `PATCH /users/me`, avatar na API, organização, plano, membros, sessões, logout global, uso, exportação ou exclusão de conta. A `/account` mostra somente o perfil real e estados indisponíveis, com as lacunas na seção 19 de `BACKEND_GAPS.md`.
- Idioma, tema e formato de data persistem em cookies porque não há endpoint de preferências da conta. O `PUT /notification-preferences` não foi usado para locale porque substitui canais e exigiria reentrada de telefone.
- O canal de privacidade precisa de `NEXT_PUBLIC_PRIVACY_CONTACT_URL` ou `NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL`. Sem configuração, a tela usa `/suporte`.
- A exclusão de conta não é automática. O diálogo exige a palavra de confirmação e encaminha ao canal de privacidade sem chamar rota destrutiva inexistente.
- O backend de testes compartilhado ocasionalmente demora a responder à consulta de sessão ou à primeira compilação do dev server. O e2e usa 1 worker e retry local para evitar falso negativo. Em CI, o retry é 2.
- `NEXT_PUBLIC_SITE_URL` precisa ser configurada em produção para os metadados absolutos. `NEXT_PUBLIC_SUPPORT_URL` continua opcional.
- O motion emite aviso de movimento reduzido no ambiente de teste. As transições ficam com duração zero e o estado final aparece.
- As páginas legais (Termos e Política) descrevem apenas o comportamento confirmado no código. Ficam pendentes de definição: identificação do controlador, CNPJ ou CPF, endereço, e-mail de contato e Encarregado (DPO), todos por variáveis `NEXT_PUBLIC_LEGAL_*`; prazos de retenção de documentos, análises, logs e traces; exclusão e exportação automáticas de dados; e confirmação jurídica das salvaguardas de transferência internacional.
- O middleware continua com a convenção `middleware.ts` herdada da F03 e o aviso de depreciação do Next 16.

## Próximos passos

1. Pedir ao backend os endpoints das seções 16, 17, 18 e 19 de `BACKEND_GAPS.md`: etapa do job, documento, campos, coordenadas, relatório, revisão, filtros, contagens, paginação com total, exportação, exclusão, payables, notificações, inteligência, perfil, organização, preferências, sessões e privacidade.
2. Trocar o progresso indeterminado por etapas reais quando `GET /api/v1/analyses/{id}/events` ou `stage` no detalhe existirem.
3. Trocar a amostra de 500 análises e payables por chamadas filtradas por página quando os endpoints aceitarem filtros, `counts` e `total`.
4. Trocar o polling de notificações por SSE quando `GET /api/v1/notifications/events` existir.
5. Pedir um PUT parcial ou token de destino para permitir editar preferências sem redigitar o telefone mascarado.
6. Trocar os cookies de idioma, tema e formato de data por preferências de conta quando `GET/PATCH /users/me/preferences` existir.
7. Implementar logout global, lista de sessões, uso, exportação e exclusão quando os endpoints das seções 19 existirem.
8. Abrir o visualizador do dossiê a partir da lista quando `document_id` e `document_url` forem expostos.
9. Construir a visão de inteligência quando o backend expuser regras, casos e métricas do classificador.
10. Definir a identificação do controlador e do Encarregado em `NEXT_PUBLIC_LEGAL_*`, os prazos de retenção e as rotas de exclusão e exportação, e então atualizar a Política de privacidade com os valores reais.
11. Revisar juridicamente os textos de Termos e Privacidade e o canal LGPD antes de produção.

## O que não foi tocado

- `backend/`, `docs/` da raiz, `infra/`, `knowledge/`, `scripts/`, `docker-compose.yml`, `Makefile` e `.env` da raiz.
- Contrato de API, tokens de design, componentes base da F02, middleware e sessão da F03.
- Dossiê da F07. A única mudança na área de verificação foi aceitar o tipo inicial em `VerificationPage` e `UploadForm` para o botão "Nova verificação".
- Shell autenticado da F04, auth da F03 e componentes base da F02 não foram alterados. As preferências de notificação usaram os hooks existentes, ampliados apenas com atualização otimista e feed por cursor.
- A F10 estendeu o `I18nProvider` e o layout raiz para o formato de data, acrescentou `react-hook-form` e `@hookform/resolvers` e criou a rota `/account`. Nenhum arquivo de auth, shell ou componente base foi editado.
- Nenhum endpoint, migration ou configuração de infraestrutura.
- Na F17, nenhum arquivo de backend, autenticação, pipeline, landing, shell ou sidebar foi alterado. As únicas mudanças fora de `lib/legal`, `features/legal`, `app/termos` e `app/privacidade` foram o `target="_blank"` nos links de aceite de `login-view.tsx`, os rótulos legais nos dicionários e o CSS de impressão.
- Nenhum commit foi criado nesta fase.
