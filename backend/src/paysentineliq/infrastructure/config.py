from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_LOCAL_DATABASE_URL = "postgresql+asyncpg://sentinel:CHANGE_ME@localhost:55432/paysentineliq"
DEFAULT_LOCAL_REDIS_URL = "redis://localhost:6379/0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "local"
    database_url: str = ""
    redis_url: str = ""
    log_level: str = "INFO"
    rate_limit_capacity: int = 60
    rate_limit_refill_per_sec: float = 1.0
    security_hash_secret: str = ""
    swr_soft_ttl_seconds: int = 30
    swr_hard_ttl_seconds: int = 300
    swr_jitter_ratio: float = 0.2
    swr_lock_ttl_seconds: int = 10
    swr_wait_timeout_seconds: float = 2.0
    allowed_hosts: str = "localhost,127.0.0.1,test,testserver,api"
    cors_allowed_origins: str = "http://localhost:3000"
    max_request_body_bytes: int = 1_048_576
    request_timeout_seconds: float = 30.0

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _apply_local_defaults_or_fail(self) -> Self:
        missing: list[str] = []

        if not self.database_url:
            if self.app_env == "local":
                self.database_url = DEFAULT_LOCAL_DATABASE_URL
            else:
                missing.append("DATABASE_URL")

        if not self.redis_url:
            if self.app_env == "local":
                self.redis_url = DEFAULT_LOCAL_REDIS_URL
            else:
                missing.append("REDIS_URL")

        if not self.security_hash_secret:
            if self.app_env == "local":
                self.security_hash_secret = "local-security-hash-secret"
            else:
                missing.append("SECURITY_HASH_SECRET")

        if self.rate_limit_capacity <= 0:
            raise ValueError("RATE_LIMIT_CAPACITY must be positive")
        if self.rate_limit_refill_per_sec <= 0:
            raise ValueError("RATE_LIMIT_REFILL_PER_SEC must be positive")
        if self.swr_hard_ttl_seconds <= self.swr_soft_ttl_seconds:
            raise ValueError("SWR_HARD_TTL_SECONDS must be greater than SWR_SOFT_TTL_SECONDS")
        if not 0.0 <= self.swr_jitter_ratio <= 1.0:
            raise ValueError("SWR_JITTER_RATIO must be between 0 and 1")
        if self.swr_lock_ttl_seconds <= 0:
            raise ValueError("SWR_LOCK_TTL_SECONDS must be positive")
        if self.swr_wait_timeout_seconds <= 0:
            raise ValueError("SWR_WAIT_TIMEOUT_SECONDS must be positive")

        if not self.allowed_hosts_list:
            raise ValueError("ALLOWED_HOSTS must not be empty")
        if "*" in self.allowed_hosts_list:
            raise ValueError("ALLOWED_HOSTS must not contain a wildcard")
        if "*" in self.cors_allowed_origins_list:
            raise ValueError("CORS_ALLOWED_ORIGINS must not contain a wildcard")
        if self.max_request_body_bytes <= 0:
            raise ValueError("MAX_REQUEST_BODY_BYTES must be positive")
        if self.request_timeout_seconds <= 0:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be positive")

        if missing:
            raise ValueError(f"missing required environment variables: {', '.join(missing)}")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
