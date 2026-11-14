# PROGRESS

## Comandos de checagem
- Segredo fora do git: `git check-ignore -v .env` (deve retornar `.gitignore:2:.env	.env`) e `git ls-files | Select-String -Pattern '^\.env$'` (deve ser vazio).
- Backend (na raiz): `make lint`, `make format-check`, `make format`, `make typecheck`, `make arch`, `make test`, `make test-docker`, `make check`.
- Equivalentes: `poetry -C backend run ruff check .`, `poetry -C backend run ruff format --check .`, `poetry -C backend run mypy src tests`, `poetry -C backend run lint-imports`, `poetry -C backend run pytest -m "not docker"`.
- Compose (na raiz): `make compose-config` (= `docker compose --env-file .env.example config --quiet`), `make up`, `make stop`.
- Graphify (regenerar o grafo; saida em `graphify-out/`): `graphify extract .` e depois `graphify cluster-only .`.
- Graphify (atualizar somente codigo): `graphify update .`.

## Estado
- Fase atual: P01 em andamento (esqueleto, qualidade e /health).
- Graphify 0.9.108 instalado; grafo gerado em `graphify-out/` (ignorado pelo git, ADR-0003).

## Historico
- P00.1 Estrutura e git: docs consolidados na raiz; `git init`; `.env` local criado e ignorado (`git check-ignore` OK; 0 arquivos `.env` rastreados). A pasta `repo/` era duplicata e foi removida.
- P00.2 Harness: PROGRESS/MEMORY atualizados; ADR-0001 (stack), ADR-0002 (score deterministico) e ADR-0003 (artefato Graphify) aceitos; checklist OWASP com as 10 categorias criado.
- P00.3 Graphify: atualizado para 0.9.108 via `uv tool install "graphifyy[gemini]" --force`; `graphify extract .` e `graphify cluster-only .` geraram `graphify-out/graph.json`, `GRAPH_REPORT.md` e `graph.html`. Pendencia: regenerar quando os documentos mudarem.
- P00.4 Commit local `chore: bootstrap sdd harness e adrs`, sem push. Pendencias bloqueantes: nenhuma.
- P01.1 Esqueleto e spec: criados `backend/src/paysentineliq` (4 camadas), `backend/tests/{unit,integration}`, `infra/postgres/init` e `frontend/` vazio; SPEC 0001 registrada. Sem codigo de produto ainda; nada a validar alem da estrutura.
- P01.2 Poetry: backend com Python 3.11.9 e `.venv` local; deps resolvidas no lock (fastapi 0.162.7, sqlalchemy 2.1.8, asyncpg 0.32.0, redis 8.1.0, alembic 1.20.1; dev: pytest 9.2.0, ruff 0.17.5, mypy 2.4.1, import-linter 2.16). `poetry install` e import do pacote OK.
- P01.3 Qualidade e Makefile: Ruff, mypy strict, pytest (marcadores) e import-linter (2 contratos) configurados; `make lint`, `make format-check`, `make typecheck` e `make arch` verdes. `test` e `test-docker` dependem da rota e do Compose.
