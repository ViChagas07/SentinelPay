POETRY ?= poetry
COMPOSE ?= docker compose --env-file .env.example
DB_REVISION_ID := $(shell python scripts/next_migration_id.py)

.PHONY: install lint format format-check typecheck arch test test-docker coverage openapi load-check build train train-guardrails backup migrate db-migrate db-revision db-check ingest-knowledge reindex-kb compose-config observability-config observability-up observability-down observability-test up stop check audit bandit security

install:
	$(POETRY) -C backend install

lint:
	$(POETRY) -C backend run ruff check .

format:
	$(POETRY) -C backend run ruff format .

format-check:
	$(POETRY) -C backend run ruff format --check .

typecheck:
	$(POETRY) -C backend run mypy src tests

arch:
	$(POETRY) -C backend run lint-imports

# chromadb e dependencia transitiva nao usada do CrewAI; o projeto usa PGVector e nao expoe Chroma.
audit:
	$(POETRY) -C backend run pip-audit --local --ignore-vuln PYSEC-2026-311 --ignore-vuln PYSEC-2026-3813 --ignore-vuln PYSEC-2026-3814 --ignore-vuln PYSEC-2026-3815

bandit:
	$(POETRY) -C backend run bandit -q -r src

security: audit bandit

test:
	$(POETRY) -C backend run pytest -m "not docker"

coverage:
	$(POETRY) -C backend run pytest -m "not docker" --cov=paysentineliq --cov-report=term-missing --cov-fail-under=80

openapi:
	$(POETRY) -C backend run python ../scripts/export_openapi.py

load-check:
	$(POETRY) -C backend run python ../scripts/load_check.py

test-docker: build up migrate
	$(POETRY) -C backend run pytest -m docker --run-docker

train:
	$(POETRY) -C backend run python -m paysentineliq.infrastructure.ml.train --output-dir ../models/artifacts

train-guardrails:
	$(POETRY) -C backend run python -m paysentineliq.infrastructure.guardrails.train --output-dir ../models/artifacts

ingest-knowledge:
	$(POETRY) -C backend run python -m paysentineliq.infrastructure.rag.ingest --env-file ../.env.example --knowledge-root ../knowledge

reindex-kb:
	$(POETRY) -C backend run python ../scripts/reindex_kb.py --env-file ../.env.example --knowledge-root ../knowledge

backup:
	python scripts/db_backup

db-migrate: backup
	$(COMPOSE) exec -T api alembic upgrade head

migrate: db-migrate

db-revision:
ifeq ($(m),)
	@echo uso: make db-revision m='descricao'
	@exit 1
else
	$(COMPOSE) run --rm -v ./backend/migrations:/app/migrations api alembic revision --autogenerate --rev-id "$(DB_REVISION_ID)" -m "$(m)"
endif

db-check:
	$(COMPOSE) exec -T api alembic check

compose-config:
	$(COMPOSE) config --quiet

observability-config:
	$(COMPOSE) --profile observability config --quiet

observability-up:
	$(COMPOSE) --profile observability up -d --build --wait

observability-down:
	$(COMPOSE) --profile observability down

observability-test:
	$(POETRY) -C backend run pytest -m observability --run-observability -q

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d --wait

stop:
	$(COMPOSE) stop

check: lint format-check typecheck arch coverage compose-config
