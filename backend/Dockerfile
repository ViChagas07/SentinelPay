# syntax=docker/dockerfile:1

FROM python:3.11.18-slim-bookworm AS builder

ENV POETRY_VERSION=2.4.1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN python -m pip install --no-cache-dir "poetry==${POETRY_VERSION}"
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root --no-ansi
COPY src ./src
RUN poetry install --only main --no-ansi

FROM python:3.11.18-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --system app && useradd --system --create-home --gid app app

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src

USER app
EXPOSE 8000
CMD ["uvicorn", "paysentineliq.interface.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
