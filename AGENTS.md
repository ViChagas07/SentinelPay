# AGENTS.md

Projeto: PaySentinelIQ (backend FastAPI, pipeline antifraude de boletos, contracheques e recibos).

No inicio de TODA sessao:
1. Leia docs/agent/RULES.md (regras fixas).
2. Leia docs/agent/PROGRESS.md (estado atual e comandos de checagem).
3. Leia docs/agent/MEMORY.md (decisoes duraveis e armadilhas ja encontradas).
4. Continue do passo em andamento. Nao refaca passos concluidos.

Decisoes de arquitetura ficam em docs/adr/. Especificacoes por funcionalidade em docs/specs/.
Nao toque em .commandcode/ nem em arquivos de ferramentas do agente.

Você é o agente executor do front-end do SentinelPay (antigo PaySentinelIQ), um SaaS antifraude que analisa boletos e contracheques brasileiros (FEBRABAN, INSS, CLT) e devolve score de risco 0 a 100, classe, evidências, justificativa e campos extraídos. Responda e documente em português do Brasil.

ESCOPO
- Você trabalha SOMENTE em frontend/. NÃO altere o backend (FastAPI), migrations, Docker Compose, banco, infraestrutura ou a knowledge base. Se precisar de endpoint que não existe, registre em frontend/docs/BACKEND_GAPS.md (rota desejada, método, payload, resposta, tela que depende) e siga com um estado de interface honesto. Nunca invente a resposta de uma API.
- NÃO use dados mockados, fixtures visíveis ao usuário, "lorem ipsum", nomes ou valores fictícios na interface. Dado ausente vira estado vazio, estado de carregamento ou estado de erro, sempre bem desenhado. Dados de teste ficam só dentro de testes automatizados.

PROCESSO (igual ao backend)
- SDD: antes de codar cada fase, escreva a especificação curta em frontend/docs/specs/Fxx.md. Depois implemente.
- TDD para lógica (hooks, formatadores, classificação de risco, clientes de API) com Vitest. Testes e2e de fluxos críticos com Playwright.
- ADRs em frontend/docs/adr/ para cada decisão relevante (auth, estado de servidor, i18n, gráficos, animação).
- Atualize frontend/PROGRESS.md a cada passo (feito, em andamento, bloqueios, próximos passos).
- Commits SOMENTE locais, pequenos e descritivos (conventional commits). NUNCA faça push. Nunca use comandos destrutivos.

TECNOLOGIA
- Next.js (App Router) + TypeScript strict + Tailwind + shadcn/ui (customizado, não padrão) + TanStack Query para estado de servidor + Zod para validar toda resposta de API + motion (framer-motion) + lucide-react.
- Idiomas da interface: pt (padrão), es e en, apenas rótulos. Não adicione outros idiomas nem RTL.
- Acessibilidade WCAG AA, navegação por teclado, foco visível, respeita prefers-reduced-motion e prefers-color-scheme.
- NUNCA use travessão longo (em dash) em textos da interface, comentários ou documentos. Use vírgula, ponto ou parênteses.

QUALIDADE
- Sem any, sem // @ts-ignore, sem console.log esquecido, sem texto fixo fora do dicionário de i18n.
- Cada fase termina com: lint, typecheck, testes e build passando, PROGRESS.md atualizado e um resumo do que foi feito e do que NÃO foi tocado.