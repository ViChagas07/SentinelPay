from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_LOCAL_DATABASE_URL = (
    "postgresql+asyncpg://sentinel:CHANGE_ME@localhost:55432/paysentineliq"
)
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

        if missing:
            raise ValueError(f"missing required environment variables: {', '.join(missing)}")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
