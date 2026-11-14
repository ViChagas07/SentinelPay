# AGENTS.md

Projeto: PaySentinelIQ (backend FastAPI, pipeline antifraude de boletos, contracheques e recibos).

No inicio de TODA sessao:
1. Leia docs/agent/RULES.md (regras fixas).
2. Leia docs/agent/PROGRESS.md (estado atual e comandos de checagem).
3. Leia docs/agent/MEMORY.md (decisoes duraveis e armadilhas ja encontradas).
4. Continue do passo em andamento. Nao refaca passos concluidos.

Decisoes de arquitetura ficam em docs/adr/. Especificacoes por funcionalidade em docs/specs/.
Nao toque em .commandcode/ nem em arquivos de ferramentas do agente.
