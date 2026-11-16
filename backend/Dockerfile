# syntax=docker/dockerfile:1

FROM python:3.11.18-slim-bookworm AS builder

ENV POETRY_VERSION=2.4.1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    POETRY_REQUESTS_TIMEOUT=300 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN python -m pip install --no-cache-dir "poetry==${POETRY_VERSION}"
COPY pyproject.toml poetry.lock ./
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --only main --no-root --no-ansi
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN poetry install --only main --no-ansi

FROM python:3.11.18-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --create-home --gid app app

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --from=builder --chown=app:app /app/alembic.ini /app/alembic.ini
COPY --from=builder --chown=app:app /app/migrations /app/migrations

RUN mkdir -p /var/run/prometheus/api /var/run/prometheus/worker /var/run/prometheus/beat && chown -R app:app /var/run/prometheus

USER app
EXPOSE 8000
CMD ["uvicorn", "paysentineliq.interface.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
