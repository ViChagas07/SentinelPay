import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.docker]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE = ["docker", "compose", "--env-file", ".env.example"]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*_COMPOSE, *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_migrations_apply() -> None:
    result = _run(["exec", "-T", "api", "alembic", "upgrade", "head"])

    assert result.returncode == 0, result.stderr


def test_alembic_version_table_is_populated() -> None:
    result = _run(
        [
            "exec",
            "-T",
            "postgres",
            "sh",
            "-c",
            'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" '
            '-tAc "SELECT version_num FROM alembic_version"',
        ]
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0003_documents"


def test_auth_tables_exist() -> None:
    result = _run(
        [
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "sentinel",
            "-d",
            "paysentineliq",
            "-tAc",
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "AND tablename IN ('users', 'refresh_tokens', 'documents') "
            "ORDER BY tablename",
        ]
    )

    assert result.returncode == 0, result.stderr
    tables = result.stdout.split()
    assert "documents" in tables
    assert "refresh_tokens" in tables
    assert "users" in tables
