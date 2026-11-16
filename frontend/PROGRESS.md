# PROGRESS do front-end

## Estado atual

- Fase atual: F11 (revisão final) concluída.
- Próxima fase: nenhuma prevista. O front-end está em estado de entrega.
- Acessibilidade: matriz axe em 16 rotas, 2 temas e 3 idiomas, com zero violações.
- Responsivo: 16 rotas em 360, 768, 1280 e 1920 px, sem rolagem horizontal; régua de risco completa no painel e no dossiê.
- i18n: 1.166 chaves completas em pt, es e en; texto fixo em JSX barrado no build.
- Sem mocks: varredura de produção zerada para mock, fixture, faker, lorem e nomes do protótipo.
- Sem travessão longo em `frontend/`; varredura incluída em `npm run check`.
- Segurança: CSP e cabeçalhos, cookies HttpOnly e Secure, 401/403/429 tratados, `npm audit` sem crítica.
- Desempenho: Lighthouse 99/100/96 na landing e 93/100/96 no painel; visualizador e gráficos sob demanda.
- Entrega: Vercel documentada, README atualizado, relatório em `docs/QUALITY.md`.
- `/account` reúne perfil, organização, preferências, atalho de notificações, segurança, privacidade e zona de perigo com navegação lateral no desktop e abas roláveis no mobile.
- Idioma, tema e formato de data aplicam imediatamente e persistem em cookies. Perfil, organização, sessões e dados mostram somente o que a API expõe, com lacunas explícitas.
- `/pagamentos` lista os payables reais, mostra resumo e linha do tempo dos próximos vencimentos, permite confirmar, pagar e ajustar vencimento, envia recibo para análise e salva lembretes globais.
- `/notificacoes` lista alertas com cursor, filtro de tipo e leitura, marca lidas com atualização otimista, mantém o badge da sidebar coerente e persiste as preferências de canal.
- `/inteligencia` mostra um estado "Em desenvolvimento" honesto, sem métricas ou gráficos inventados, até existir endpoint de regras, casos e modelos.
- `/boletos` e `/folha` listam as análises por classe, com contagens, filtros, ordenação, paginação e estado na URL.
- As listas usam a amostra real de até 500 análises obtida por cursor, porque a API ainda não oferece filtros, totais nem os campos extraídos. A interface explica a limitação e mostra "+" quando a amostra é truncada.
- `/verificacao` e `/verificacao/nova` enviam PDF ou imagem, criam o job e acompanham o pipeline por polling.
- `/verificacao/[id]` mostra o dossiê com score, classe, justificativa, evidências, campos, metadados e avisos honestos.
- Painel da F06, landing da F05, shell da F04, sessão da F03 e design system da F02 preservados.
- Backend, migrations, Compose, banco, infraestrutura e knowledge base: intocados.

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
10. Revisar juridicamente os textos de Termos e Privacidade e o canal LGPD antes de produção.

## O que não foi tocado

- `backend/`, `docs/` da raiz, `infra/`, `knowledge/`, `scripts/`, `docker-compose.yml`, `Makefile` e `.env` da raiz.
- Contrato de API, tokens de design, componentes base da F02, middleware e sessão da F03.
- Dossiê da F07. A única mudança na área de verificação foi aceitar o tipo inicial em `VerificationPage` e `UploadForm` para o botão "Nova verificação".
- Shell autenticado da F04, auth da F03 e componentes base da F02 não foram alterados. As preferências de notificação usaram os hooks existentes, ampliados apenas com atualização otimista e feed por cursor.
- A F10 estendeu o `I18nProvider` e o layout raiz para o formato de data, acrescentou `react-hook-form` e `@hookform/resolvers` e criou a rota `/account`. Nenhum arquivo de auth, shell ou componente base foi editado.
- Nenhum endpoint, migration ou configuração de infraestrutura.
- Nenhum commit foi criado nesta fase.
