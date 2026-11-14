import secrets
from functools import lru_cache
from typing import Literal, Self

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_LOCAL_DATABASE_URL = "postgresql+asyncpg://sentinel:CHANGE_ME@localhost:55432/paysentineliq"
DEFAULT_LOCAL_REDIS_URL = "redis://localhost:6379/0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
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
    bruteforce_max_attempts: int = 5
    bruteforce_window_seconds: int = 900
    bruteforce_base_block_seconds: int = 30
    bruteforce_max_block_seconds: int = 3600
    ssrf_allowed_hosts: str = "localhost,127.0.0.1"
    jwt_secret: str = Field(
        default="",
        validation_alias=AliasChoices("JWT_SECRET", "JWT_SECRET_KEY"),
    )
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_ttl_minutes: int = Field(
        default=15,
        validation_alias=AliasChoices(
            "ACCESS_TOKEN_TTL_MINUTES",
            "ACCESS_TOKEN_EXPIRE_MINUTES",
        ),
    )
    refresh_token_ttl_days: int = Field(
        default=7,
        validation_alias=AliasChoices(
            "REFRESH_TOKEN_TTL_DAYS",
            "REFRESH_TOKEN_EXPIRE_DAYS",
        ),
    )
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    google_authorization_endpoint: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_token_endpoint: str = "https://oauth2.googleapis.com/token"
    google_jwks_uri: str = "https://www.googleapis.com/oauth2/v3/certs"
    google_issuer: str = "https://accounts.google.com"
    frontend_url: str = ""
    cookie_domain: str = ""
    oidc_state_ttl_seconds: int = 600
    s3_endpoint_url: str = ""
    s3_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("S3_REGION", "AWS_REGION"),
    )
    s3_bucket: str = "paysentineliq-documents"
    s3_access_key_id: str = Field(
        default="",
        validation_alias=AliasChoices(
            "S3_ACCESS_KEY_ID",
            "AWS_ACCESS_KEY_ID",
        ),
    )
    s3_secret_access_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "S3_SECRET_ACCESS_KEY",
            "AWS_SECRET_ACCESS_KEY",
        ),
    )
    upload_max_mb: int = 25
    pdf_max_pages: int = 50
    s3_presigned_url_ttl_seconds: int = 300
    ocr_langs: str = "pt,es,en"
    ocr_max_pages: int = 20
    ocr_render_dpi: int = 200
    ocr_timeout_seconds: float = 120.0
    ocr_max_image_pixels: int = 25_000_000
    ocr_native_min_chars: int = 40
    embedding_base_url: str = ""
    embedding_model: str = ""
    embedding_dim: int = 0
    embedding_api_key: str = ""
    embedding_timeout_seconds: float = 30.0
    embedding_batch_size: int = 32
    embedding_max_retries: int = 3
    embedding_retry_backoff_seconds: float = 1.0
    vector_store: Literal["pgvector", "pinecone"] = "pgvector"
    pinecone_api_key: str = ""
    pinecone_index: str = ""
    pinecone_namespace: str = "knowledge"
    rag_chunk_size: int = 1200
    rag_chunk_overlap: int = 150
    rag_fake_embedder: bool = False
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_temperature: float = 0.1
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2
    llm_max_output_tokens: int = 800
    llm_max_score_adjustment: int = 5
    llm_language: str = "pt"
    ai_node_timeout_seconds: float = 60.0

    @property
    def ocr_languages_list(self) -> list[str]:
        return [
            language.strip().lower() for language in self.ocr_langs.split(",") if language.strip()
        ]

    @property
    def google_configured(self) -> bool:
        return bool(
            self.google_client_id and self.google_client_secret and self.google_redirect_uri
        )

    @property
    def s3_configured(self) -> bool:
        return bool(self.s3_bucket and self.s3_access_key_id and self.s3_secret_access_key)

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def ssrf_allowed_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.ssrf_allowed_hosts.split(",") if host.strip()]

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
                self.security_hash_secret = secrets.token_urlsafe(32)
            else:
                missing.append("SECURITY_HASH_SECRET")

        if not self.jwt_secret:
            if self.app_env == "local":
                self.jwt_secret = secrets.token_urlsafe(48)
            else:
                missing.append("JWT_SECRET")

        if self.app_env != "local":
            for name, value in (
                ("GOOGLE_CLIENT_ID", self.google_client_id),
                ("GOOGLE_CLIENT_SECRET", self.google_client_secret),
                ("GOOGLE_REDIRECT_URI", self.google_redirect_uri),
                ("FRONTEND_URL", self.frontend_url),
                ("S3_BUCKET", self.s3_bucket),
                ("S3_ACCESS_KEY_ID", self.s3_access_key_id),
                ("S3_SECRET_ACCESS_KEY", self.s3_secret_access_key),
            ):
                if not value:
                    missing.append(name)
            if self.jwt_secret and len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters")

        if self.access_token_ttl_minutes <= 0:
            raise ValueError("ACCESS_TOKEN_TTL_MINUTES must be positive")
        if self.refresh_token_ttl_days <= 0:
            raise ValueError("REFRESH_TOKEN_TTL_DAYS must be positive")
        if self.oidc_state_ttl_seconds <= 0:
            raise ValueError("OIDC_STATE_TTL_SECONDS must be positive")
        if self.upload_max_mb <= 0:
            raise ValueError("UPLOAD_MAX_MB must be positive")
        if self.pdf_max_pages <= 0:
            raise ValueError("PDF_MAX_PAGES must be positive")
        if self.s3_presigned_url_ttl_seconds <= 0:
            raise ValueError("S3_PRESIGNED_URL_TTL_SECONDS must be positive")
        languages = self.ocr_languages_list
        if not languages:
            raise ValueError("OCR_LANGS must not be empty")
        if set(languages) - {"pt", "es", "en"}:
            raise ValueError("OCR_LANGS supports only pt, es and en")
        if self.ocr_max_pages <= 0:
            raise ValueError("OCR_MAX_PAGES must be positive")
        if self.ocr_render_dpi <= 0:
            raise ValueError("OCR_RENDER_DPI must be positive")
        if self.ocr_timeout_seconds <= 0:
            raise ValueError("OCR_TIMEOUT_SECONDS must be positive")
        if self.ocr_max_image_pixels <= 0:
            raise ValueError("OCR_MAX_IMAGE_PIXELS must be positive")
        if self.ocr_native_min_chars < 0:
            raise ValueError("OCR_NATIVE_MIN_CHARS must be non-negative")
        if self.embedding_dim < 0:
            raise ValueError("EMBEDDING_DIM must be non-negative")
        if self.embedding_timeout_seconds <= 0:
            raise ValueError("EMBEDDING_TIMEOUT_SECONDS must be positive")
        if self.embedding_batch_size <= 0:
            raise ValueError("EMBEDDING_BATCH_SIZE must be positive")
        if self.embedding_max_retries < 0:
            raise ValueError("EMBEDDING_MAX_RETRIES must be non-negative")
        if self.embedding_retry_backoff_seconds < 0:
            raise ValueError("EMBEDDING_RETRY_BACKOFF_SECONDS must be non-negative")
        if self.rag_chunk_size <= 0:
            raise ValueError("RAG_CHUNK_SIZE must be positive")
        if not 0 <= self.rag_chunk_overlap < self.rag_chunk_size:
            raise ValueError("RAG_CHUNK_OVERLAP must be between 0 and RAG_CHUNK_SIZE")
        if not 0.0 <= self.llm_temperature <= 1.0:
            raise ValueError("LLM_TEMPERATURE must be between 0 and 1")
        if self.llm_timeout_seconds <= 0:
            raise ValueError("LLM_TIMEOUT_SECONDS must be positive")
        if self.llm_max_retries < 0:
            raise ValueError("LLM_MAX_RETRIES must be non-negative")
        if self.llm_max_output_tokens <= 0:
            raise ValueError("LLM_MAX_OUTPUT_TOKENS must be positive")
        if not 0 <= self.llm_max_score_adjustment <= 20:
            raise ValueError("LLM_MAX_SCORE_ADJUSTMENT must be between 0 and 20")
        if self.llm_language not in ("pt", "es", "en"):
            raise ValueError("LLM_LANGUAGE must be pt, es or en")
        if self.ai_node_timeout_seconds <= 0:
            raise ValueError("AI_NODE_TIMEOUT_SECONDS must be positive")

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
        if self.bruteforce_max_attempts <= 0:
            raise ValueError("BRUTEFORCE_MAX_ATTEMPTS must be positive")
        if self.bruteforce_window_seconds <= 0:
            raise ValueError("BRUTEFORCE_WINDOW_SECONDS must be positive")
        if self.bruteforce_base_block_seconds <= 0:
            raise ValueError("BRUTEFORCE_BASE_BLOCK_SECONDS must be positive")
        if self.bruteforce_max_block_seconds < self.bruteforce_base_block_seconds:
            raise ValueError(
                "BRUTEFORCE_MAX_BLOCK_SECONDS must be >= BRUTEFORCE_BASE_BLOCK_SECONDS"
            )
        if "*" in self.ssrf_allowed_hosts_list:
            raise ValueError("SSRF_ALLOWED_HOSTS must not contain a wildcard")

        if missing:
            raise ValueError(f"missing required environment variables: {', '.join(missing)}")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
