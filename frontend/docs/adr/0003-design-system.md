# ADR 0003: Design system e catálogo interno

- Status: aceito
- Data: 2026-11-15
- Fase: F02

## Contexto

A F02 define a linguagem visual do produto antes das telas de negócio. O sistema precisa ser editorial, denso e acessível, com componentes reutilizáveis, movimento discreto e uma rota interna de revisão. Os tokens da F01 não foram alterados; os componentes apenas os consomem.

## Decisão

### Superfícies e forma

- Raios de 6px nas superfícies, controles e sobreposições.
- Bordas de 1px no lugar de sombras. Cards, diálogos, menus, popovers e toasts não usam sombra.
- Sem gradiente decorativo e sem glassmorphism. O header é sólido.
- A única animação de gradiente é o shimmer funcional do Skeleton, que respeita `prefers-reduced-motion`.
- Cores de risco aparecem somente em RiskRuler, RiskStamp, RiskBadge, ClassDot, StripChart e no favicon de alerta. Texto de risco usa a cor de texto do tema, nunca a cor de risco como cor de texto pequeno.

### Risco

- `RiskRuler` recebe `score` e `band`. A classe, a cor e o rótulo vêm de `band` através de `lib/risk/presentation.ts`. O score só posiciona o marcador.
- `RISK_BAND_LAYOUT` existe apenas para desenhar as faixas e os rótulos de faixa. Não existe função que converta score em classe.
- As variantes compacta, média e grande mostram número em mono e classe em texto. A compacta cabe em linha de tabela.
- `RiskStamp` é estático, com rotação leve e sem animação em loop.
- `RiskBadge` e `ClassDot` usam a mesma apresentação de `lib/risk`. O ponto é decorativo e sempre acompanha texto visível.

### Dados e evidências

- `DataTable` é genérica, recebe colunas tipadas e usa `lib/table/sort.ts` para ordenação estável.
- A tabela usa `table-fixed`, quebra identificadores em mono e não permite rolagem horizontal.
- No mobile, a tabela vira lista empilhada com `dl`, e a ordenação fica em um Select compacto.
- Loading usa Skeleton com shimmer. Vazio e erro são estados explícitos.
- `EvidenceItem` mostra gravidade, framework, regra e trecho. O realce é controlado por `highlighted`, permitindo sincronizar com o visualizador de documento no futuro. O realce usa petróleo, não a paleta de risco.

### Gráficos

- `StripChart` e `Sparkline` são SVG próprios, sem biblioteca de gráfico.
- O StripChart usa barras empilhadas por classe, rótulos diretos de total e eixo de 1px. A legenda é textual, com linhas de 1px, sem bolinhas.
- Rótulos de dia usam HTML para manter legibilidade em larguras pequenas.
- Há uma tabela `sr-only` dentro de um wrapper `sr-only` para leitores de tela. O wrapper evita que a tabela expanda a largura do documento no mobile.
- O Sparkline é uma linha de 1px, sem área suave.

### Movimento

- `RiskRuler` anima o marcador com mola ao entrar. O estado inicial é o mesmo no servidor e no cliente para evitar erro de hidratação. Com movimento reduzido, a transição tem duração zero.
- `PageTransition` usa animação CSS de 200 ms com fade e subida leve. A escolha evita conteúdo invisível no SSR e permite que `prefers-reduced-motion` desligue a animação sem divergência de hidratação.
- `Stagger`, `CountUp` e `Presence` usam motion. CountUp usa dois spans com variantes `motion-safe` e `motion-reduce` para não divergir entre servidor e cliente.
- Nenhuma animação é decorativa, em loop ou bloqueante. Toasts, diálogos e sheets entram apenas quando abertos.

### Sobreposições e primitivos

- Toast usa sonner com classes e variáveis do projeto. Ícones são neutros, sem cores de risco.
- Tooltip, Dialog, Sheet, Tabs, Select e Command usam Radix e cmdk, com bordas de 1px, raio de 6px e tipografia do projeto.
- O Command é uma paleta de navegação da rota interna, com atalho Ctrl K.
- O Select do Radix esconde o restante da página com `aria-hidden` enquanto aberto. A auditoria axe do estado aberto foca no conteúdo da sobreposição e exclui o fundo oculto, que já é auditado fechado.

### Rota interna

- `/dev/design` mostra todos os componentes, com controles de tema e idioma no header.
- `proxy.ts` bloqueia a rota fora de `NODE_ENV=development` com 404. A página também chama `notFound()` como defesa em profundidade.
- A página é `force-dynamic` e não é indexável.
- Amostras de tabela, gráfico e evidência existem apenas nessa rota, sempre rotuladas como demonstração. Nenhuma tela de negócio usa dado mockado.

### Acessibilidade

- Axe roda em 2 temas e 3 idiomas, sem violações, em `e2e/design-accessibility.spec.ts`.
- Sobreposições abertas são auditadas em `e2e/design-overlays.spec.ts`.
- O layout mobile é validado sem rolagem horizontal em `e2e/design-layout.spec.ts`.
- Screenshots claros e escuros são gerados em `docs/design/` por `e2e/design-screenshots.spec.ts`.

## Consequências

- Telas de negócio devem reutilizar estes componentes e não recriar réguas, badges, tabelas ou gráficos.
- Cores de risco não podem ser usadas como decoração em nenhuma tela.
- Novos componentes precisam de entrada em `/dev/design` e, quando tiverem sobreposição, teste de axe aberto.
- O bloqueio de produção depende do `proxy.ts`; a checagem em página sozinha pode responder 200 com shell de streaming.
- A autenticação continua fora desta fase e deve ser tratada em fase própria.
