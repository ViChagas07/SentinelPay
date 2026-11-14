# PROGRESS

## Comandos de checagem
- Segredo fora do git: `git check-ignore -v .env` (deve retornar `.gitignore:2:.env	.env`) e `git ls-files | Select-String -Pattern '^\.env$'` (deve ser vazio).
- Graphify (regenerar o grafo; saida em `graphify-out/`): `graphify extract .` e depois `graphify cluster-only .`.
- Graphify (atualizar somente codigo): `graphify update .`.
- A partir da P01, anotar aqui os comandos reais de testes, Ruff, formatacao, mypy e import-linter quando existirem.

## Estado
- Fase atual: P00 concluida (bootstrap SDD, harness, ADRs). Proximo passo: P01, conforme instrucao do dono.
- Graphify 0.9.108 instalado; grafo gerado em `graphify-out/` (ignorado pelo git, ADR-0003).

## Historico
- P00.1 Estrutura e git: docs consolidados na raiz; `git init`; `.env` local criado e ignorado (`git check-ignore` OK; 0 arquivos `.env` rastreados). A pasta `repo/` era duplicata e foi removida.
- P00.2 Harness: PROGRESS/MEMORY atualizados; ADR-0001 (stack), ADR-0002 (score deterministico) e ADR-0003 (artefato Graphify) aceitos; checklist OWASP com as 10 categorias criado.
- P00.3 Graphify: atualizado para 0.9.108 via `uv tool install "graphifyy[gemini]" --force`; `graphify extract .` e `graphify cluster-only .` geraram `graphify-out/graph.json`, `GRAPH_REPORT.md` e `graph.html`. Pendencia: regenerar quando os documentos mudarem.
- P00.4 Commit local `chore: bootstrap sdd harness e adrs`, sem push. Pendencias bloqueantes: nenhuma.
