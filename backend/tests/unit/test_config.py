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
        metrics_token="production-metrics-token",
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


def test_retrieval_defaults_are_local_and_cpu_only() -> None:
    settings = Settings(app_env="local")

    assert settings.retrieval_top_k == 25
    assert settings.rerank_top_n == 4
    assert settings.rerank_enabled is True
    assert settings.embedder_backend == "onnx"
    assert settings.reranker_backend == "onnx"
    assert settings.rerank_max_length == 512
    assert settings.batch_size == 16
    assert settings.torch_num_threads == 0
    assert settings.rerank_timeout_seconds == 30.0


def test_rerank_top_n_must_not_exceed_top_k() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="local", retrieval_top_k=2, rerank_top_n=3)


def test_retrieval_backend_rejects_non_cpu_values() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"app_env": "local", "embedder_backend": "cuda"})
    with pytest.raises(ValidationError):
        Settings.model_validate({"app_env": "local", "reranker_backend": "rocm"})


def test_retrieval_batch_and_threads_must_be_valid() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="local", batch_size=0)
    with pytest.raises(ValidationError):
        Settings(app_env="local", torch_num_threads=-1)


def test_hybrid_retrieval_defaults_keep_old_path_off() -> None:
    settings = Settings(app_env="local")

    assert settings.hybrid_retrieval_enabled is False
    assert settings.hybrid_fusion == "rrf"
    assert settings.hybrid_rrf_k == 60
    assert settings.hybrid_dense_weight == 0.6
    assert settings.hybrid_sparse_weight == 0.4
    assert settings.query_embedding_cache_ttl_seconds == 3600


def test_remote_reranker_settings_are_supported() -> None:
    settings = Settings(
        app_env="local",
        reranker_backend="remote",
        reranker_remote_url="https://reranker.example/v1/rerank",
        reranker_remote_api_key="secret",
        reranker_remote_model="remote-reranker",
        rerank_timeout_seconds=2.5,
    )

    assert settings.reranker_backend == "remote"
    assert settings.reranker_remote_url == "https://reranker.example/v1/rerank"
    assert settings.rerank_timeout_seconds == 2.5


def test_rerank_timeout_and_remote_url_are_validated() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="local", rerank_timeout_seconds=0)
    with pytest.raises(ValidationError):
        Settings(app_env="local", reranker_remote_url="ftp://reranker.example")


def test_hybrid_fusion_settings_are_validated() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="local", hybrid_rrf_k=0)
    with pytest.raises(ValidationError):
        Settings(app_env="local", hybrid_dense_weight=0.0, hybrid_sparse_weight=0.0)
    with pytest.raises(ValidationError):
        Settings(app_env="local", hybrid_dense_weight=-0.1)
    with pytest.raises(ValidationError):
        Settings(app_env="local", query_embedding_cache_ttl_seconds=0)
    with pytest.raises(ValidationError):
        Settings.model_validate({"app_env": "local", "hybrid_fusion": "magic"})


def test_langfuse_defaults_are_disabled() -> None:
    settings = Settings(app_env="local")

    assert settings.langfuse_enabled is False
    assert settings.langfuse_public_key == ""
    assert settings.langfuse_secret_key == ""
    assert settings.langfuse_host == ""
    assert settings.langfuse_base_url == ""
    assert settings.langfuse_sample_rate == 1.0


def test_langfuse_settings_are_validated() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="local", langfuse_sample_rate=1.5)
    with pytest.raises(ValidationError):
        Settings(app_env="local", langfuse_sample_rate=-0.1)
    with pytest.raises(ValidationError):
        Settings(app_env="local", langfuse_host="ftp://langfuse.example")
    with pytest.raises(ValidationError):
        Settings(app_env="local", langfuse_base_url="ftp://langfuse.example")
