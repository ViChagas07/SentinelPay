POETRY ?= poetry
COMPOSE ?= docker compose --env-file .env.example
DB_REVISION_ID := $(shell python scripts/next_migration_id.py)

.PHONY: install lint format format-check typecheck arch test test-docker train backup migrate db-migrate db-revision db-check compose-config up stop check audit bandit security

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

audit:
	$(POETRY) -C backend run pip-audit --local

bandit:
	$(POETRY) -C backend run bandit -q -r src

security: audit bandit

test:
	$(POETRY) -C backend run pytest -m "not docker"

test-docker: up migrate
	$(POETRY) -C backend run pytest -m docker --run-docker

train:
	$(POETRY) -C backend run python -m paysentineliq.infrastructure.ml.train --output-dir ../models/artifacts

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

up:
	$(COMPOSE) up -d --wait

stop:
	$(COMPOSE) stop

check: lint format-check typecheck arch test compose-config
