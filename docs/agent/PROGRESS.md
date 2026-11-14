# PROGRESS

## Comandos de checagem
- Segredo fora do git: `git check-ignore -v .env` (deve retornar `.gitignore:2:.env	.env`) e `git ls-files | Select-String -Pattern '^\.env$'` (deve ser vazio).
- Backend (na raiz): `make lint`, `make format-check`, `make format`, `make typecheck`, `make arch`, `make test`, `make test-docker`, `make check`.
- Backup/migration: `make backup` (grava `backups/*.sql`), `make migrate` (backup + `alembic upgrade head` no container da API).
- Equivalentes: `poetry -C backend run ruff check .`, `poetry -C backend run ruff format --check .`, `poetry -C backend run mypy src tests`, `poetry -C backend run lint-imports`, `poetry -C backend run pytest -m "not docker"`.
- Compose (na raiz): `make compose-config` (= `docker compose --env-file .env.example config --quiet`), `make up`, `make stop`.
- Graphify (regenerar o grafo; saida em `graphify-out/`): `graphify extract .` e depois `graphify cluster-only .`.
- Graphify (atualizar somente codigo): `graphify update .`.

## Estado
- Fase atual: P03 em andamento (seguranca, rate limit e cache SWR). P02 concluida.
- Stack local no ar com 6 servicos saudaveis; `/health` 200, `/ready` 200 e migration `0001_initial` aplicada. Graphify 0.9.108 instalado; grafo em `graphify-out/` (ignorado, ADR-0003).

## Historico
- P00.1 Estrutura e git: docs consolidados na raiz; `git init`; `.env` local criado e ignorado (`git check-ignore` OK; 0 arquivos `.env` rastreados). A pasta `repo/` era duplicata e foi removida.
- P00.2 Harness: PROGRESS/MEMORY atualizados; ADR-0001 (stack), ADR-0002 (score deterministico) e ADR-0003 (artefato Graphify) aceitos; checklist OWASP com as 10 categorias criado.
- P00.3 Graphify: atualizado para 0.9.108 via `uv tool install "graphifyy[gemini]" --force`; `graphify extract .` e `graphify cluster-only .` geraram `graphify-out/graph.json`, `GRAPH_REPORT.md` e `graph.html`. Pendencia: regenerar quando os documentos mudarem.
- P00.4 Commit local `chore: bootstrap sdd harness e adrs`, sem push. Pendencias bloqueantes: nenhuma.
- P01.1 Esqueleto e spec: criados `backend/src/paysentineliq` (4 camadas), `backend/tests/{unit,integration}`, `infra/postgres/init` e `frontend/` vazio; SPEC 0001 registrada. Sem codigo de produto ainda; nada a validar alem da estrutura.
- P01.2 Poetry: backend com Python 3.11.9 e `.venv` local; deps resolvidas no lock (fastapi 0.162.7, sqlalchemy 2.1.8, asyncpg 0.32.0, redis 8.1.0, alembic 1.20.1; dev: pytest 9.2.0, ruff 0.17.5, mypy 2.4.1, import-linter 2.16). `poetry install` e import do pacote OK.
- P01.3 Qualidade e Makefile: Ruff, mypy strict, pytest (marcadores) e import-linter (2 contratos) configurados; `make lint`, `make format-check`, `make typecheck` e `make arch` verdes. `test` e `test-docker` dependem da rota e do Compose.
- P01.4 Health (TDD): teste unitario falhou por ausencia do app e passou depois de `GET /health`; 2 testes verdes (200 com corpo exato e 405 para POST). Ruff, format, mypy strict e import-linter verdes. A rota nao toca banco nem Redis.
- P01.5 Infra e Docker: Dockerfile multi-stage com usuario `app` (uid 999); Compose com Postgres+pgvector (55432), Redis, RabbitMQ, MinIO (ADR-0004), Mailpit e API; volumes nomeados e healthchecks. `make up` OK, `/health` 200, extensao `vector` presente e `make test-docker` com 1 teste verde.
- P01.6 Checagens finais: `make check` verde (Ruff, format, mypy, import-linter, 2 testes unitarios e `docker compose config --quiet`). Compose usa `.env.example`, nunca o `.env` de producao.
- P02.1 Spec e ADR: SPEC 0002 e ADR-0005 registram configuracao, DI, UoW, erros problem+json, logs, locale e readiness. Sem codigo de negocio; nada a validar alem dos documentos.
- P02.2 Config: `Settings` com pydantic-settings lendo so ambiente (`env_file=None`), defaults locais e falha na inicializacao fora de local sem `DATABASE_URL`/`REDIS_URL`; 5 testes verdes. Ruff, mypy strict e import-linter verdes.
- P02.3 Logs e request_id: logger JSON no stdout com `ContextVar`, middleware que aceita/gera `X-Request-ID` e filtro de PII (CPF, CNPJ, e-mail, telefone, JWT, Bearer, chaves e segredos); 16 testes de logging/request_id verdes, alem dos 2 de health. Ruff, mypy e import-linter verdes.
- P02.4 Erros e locale: hierarquia `DomainError`/`NotFoundError`/`ApplicationError`; handlers problem+json para dominio, validacao, HTTP e 500 generico sem stack/PII; resolvedor `Accept-Language` com 9 locales e fallback `en`; 44 testes unitarios verdes, Ruff/mypy/import-linter/format verdes.
- P02.5 Banco/UoW/Alembic: engine async com asyncpg, sessao por requisicao, portas `UnitOfWork`/`ExampleRepository`, adaptadores SQLAlchemy, `Base` com UUID/timestamps e Alembic async com migration vazia; 46 testes unitarios verdes, Ruff/mypy/import-linter verdes. Testes docker e `alembic upgrade head` ficam para o passo de backup.
- P02.6 Ready e rota de exemplo: `/ready` checa Postgres e Redis; rota removivel `/api/v1/example/{id}` executa SELECT via UoW, resolve locale/request_id e mapeia `document_not_found`. Access log do uvicorn desativado para nao vazar query string; 55 testes unitarios e 7 docker verdes. Mascara de telefone refinada para nao corromper UUIDs em logs.
- P02.7 Backup/migration: `make backup` gerou dump de 974 bytes (nao vazio); `make migrate` executou backup e `alembic upgrade head` no container; `alembic_version=0001_initial` confirmado. `make check` e `make test-docker` verdes; stack no ar.
- P02.8 Prova liveness/readiness: com Postgres e Redis parados, `/health` continuou 200 e `/ready` retornou 503 com ambos os checks falsos; apos `start` + `make up`, `/ready` voltou a 200. Nenhuma alteracao de codigo; stack restaurada.
- P03.1 Spec e ADR: SPEC 0003 e ADR-0006 definem rate limit Token Bucket, SWR, headers/CORS/TrustedHost, CSRF, SSRF com pinagem, forca bruta, limites e auditoria. Sem codigo ainda.
- P03.2 Rate limit: Token Bucket Lua atomico por IP/usuario com chaves pseudonimizadas, 429 com `Retry-After`, fail-open fora de auth e 503 em `/api/v1/auth/*`; 11 testes unitarios e teste de concorrencia Redis (20 chamadas, 5 permitidas) verdes. Suite unitaria 61 verdes.
