# SPEC 0001: Estrutura do monorepo e health

## Objetivo
Criar o esqueleto executavel do backend e da infraestrutura local, com ferramentas de qualidade e a rota `GET /health`.

## Requisitos (RF) e nao funcionais (RNF)
- RF1: monorepo com `backend/` (`src/paysentineliq/{domain,application,infrastructure,interface}` e `tests/{unit,integration}`), `infra/` para configs e `frontend/` reservado para fase futura.
- RF2: Poetry com Python `>=3.11,<3.12` e apenas as dependencias do nucleo.
- RF3: Ruff (lint e format), mypy strict, pytest e import-linter configurados no `pyproject.toml`.
- RF4: Makefile com `install`, `lint`, `format`, `typecheck`, `arch`, `test`, `test-docker`, `up`, `stop` e `check`.
- RF5: Compose com PostgreSQL+pgvector, Redis, RabbitMQ (management), MinIO, Mailpit e API; volumes nomeados e healthcheck em todos.
- RF6: Dockerfile multi-stage, usuario nao root e sem copiar `.env`.
- RF7: `GET /health` responde `200` com `{"status":"ok"}` sem acessar banco nem Redis.
- RNF1: sem segredos no repositorio; variaveis do Compose vem de `.env`/`.env.example`.
- RNF2: imagens com tag fixa; artefatos gerados fora do git.
- RNF3: codigo e identificadores em ingles; documentacao em pt-BR.

## Fora do escopo
Autenticacao, modelos e tabelas, migrations, Celery, bibliotecas de IA, OCR, frontend e qualquer rota alem de `/health`.

## Contrato (endpoints, schemas, eventos)
- `GET /health` -> `200 application/json` com corpo exato `{"status":"ok"}`.
- Sem autenticacao. Liveness puro: nao consulta PostgreSQL, Redis ou qualquer dependencia.
- `POST /health` -> `405`.

## Criterios de aceite (cada um vira pelo menos um teste)
1. Teste unitario: `GET /health` retorna `200` e o corpo exato.
2. Teste unitario: metodo diferente de `GET` retorna `405`.
3. Teste docker: `/health` responde `200` com o Compose no ar.
4. `import-linter` passa; `domain` e `application` nao importam frameworks.
5. `ruff check`, `ruff format --check`, `mypy` e `pytest` passam.
6. `docker compose --env-file .env.example config --quiet` passa.

## Casos de borda e de abuso
- A resposta nao expoe versao, ambiente, dependencias ou stack trace.
- Chamadas repetidas nao geram carga em banco ou Redis.
- O endpoint nao aceita metodos diferentes de `GET`.

## Plano de testes (TDD: teste falho primeiro)
1. Escrever `test_health.py` e confirmar a falha por ausencia do app.
2. Implementar o app minimo e confirmar a passagem.
3. Subir o Compose e executar o teste marcado como `docker`.
4. Rodar Ruff, mypy, import-linter e pytest; corrigir violacoes.

## Riscos e NAO VALIDADO
- Docker daemon indisponivel: `up` e o teste docker ficam NAO VALIDADO.
- A imagem oficial do MinIO saiu dos registries publicos em 2026; usar imagem comunitaria fixada apenas no ambiente local (ADR-0004).
- O `.env` local contem credenciais de producao e nao deve ser usado pelo Compose local; o Makefile usa `.env.example`.
