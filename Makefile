POETRY ?= poetry
COMPOSE ?= docker compose --env-file .env.example

.PHONY: install lint format format-check typecheck arch test test-docker backup migrate compose-config up stop check audit bandit security

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

test-docker: up
	$(POETRY) -C backend run pytest -m docker --run-docker

backup:
	python scripts/db_backup

migrate: backup
	$(COMPOSE) exec -T api alembic upgrade head

compose-config:
	$(COMPOSE) config --quiet

up:
	$(COMPOSE) up -d --wait

stop:
	$(COMPOSE) stop

check: lint format-check typecheck arch test compose-config
