from pathlib import Path

import pytest
from pydantic import ValidationError

from paysentineliq.infrastructure.config import (
    DEFAULT_LOCAL_DATABASE_URL,
    DEFAULT_LOCAL_REDIS_URL,
    Settings,
)


def test_local_uses_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_ENV", "DATABASE_URL", "REDIS_URL"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(app_env="local")

    assert settings.app_env == "local"
    assert settings.database_url == DEFAULT_LOCAL_DATABASE_URL
    assert settings.redis_url == DEFAULT_LOCAL_REDIS_URL


def test_non_local_requires_external_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "REDIS_URL"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError) as error:
        Settings(app_env="production", database_url="", redis_url="")

    message = str(error.value)
    assert "DATABASE_URL" in message
    assert "REDIS_URL" in message


def test_non_local_accepts_external_urls() -> None:
    settings = Settings(
        app_env="production",
        database_url="postgresql+asyncpg://user:pass@db:5432/app",
        redis_url="redis://cache:6379/0",
        rabbitmq_url="amqp://user:pass@rabbitmq:5672//",
        celery_result_backend="redis://cache:6379/1",
        security_hash_secret="production-secret",
        jwt_secret="x" * 64,
        google_client_id="test-client",
        google_client_secret="test-secret",
        google_redirect_uri="https://example.com/api/v1/auth/google/callback",
        frontend_url="https://app.example.com",
        s3_bucket="test-bucket",
        s3_access_key_id="test-key",
        s3_secret_access_key="test-secret",
    )

    assert settings.app_env == "production"
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_reads_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://env-db/app")
    monkeypatch.setenv("REDIS_URL", "redis://env-redis:6379/0")

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://env-db/app"
    assert settings.redis_url == "redis://env-redis:6379/0"


def test_does_not_read_dotenv_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "DATABASE_URL=postgresql+asyncpg://from-file/app\nREDIS_URL=redis://from-file:6379/0\n",
        encoding="utf-8",
    )
    for name in ("APP_ENV", "DATABASE_URL", "REDIS_URL"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(app_env="local")

    assert "from-file" not in settings.database_url
    assert "from-file" not in settings.redis_url


def test_security_lists_are_parsed() -> None:
    settings = Settings(
        app_env="local",
        allowed_hosts="localhost, 127.0.0.1,api",
        cors_allowed_origins="http://localhost:3000, https://app.example",
    )

    assert settings.allowed_hosts_list == ["localhost", "127.0.0.1", "api"]
    assert settings.cors_allowed_origins_list == [
        "http://localhost:3000",
        "https://app.example",
    ]


def test_cors_wildcard_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="local", cors_allowed_origins="*")


def test_allowed_hosts_wildcard_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="local", allowed_hosts="*")


def test_local_generates_jwt_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("JWT_SECRET", "JWT_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(app_env="local")

    assert len(settings.jwt_secret) >= 32
    assert settings.google_configured is False


def test_jwt_secret_reads_production_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("JWT_SECRET_KEY", "y" * 64)

    settings = Settings(app_env="local")

    assert settings.jwt_secret == "y" * 64


def test_ocr_languages_are_parsed() -> None:
    settings = Settings(app_env="local", ocr_langs="PT, es,en")

    assert settings.ocr_languages_list == ["pt", "es", "en"]


def test_unsupported_ocr_language_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="local", ocr_langs="pt,de")
