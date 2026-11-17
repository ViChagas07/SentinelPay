import secrets
from functools import lru_cache
from typing import Literal, Self
from urllib.parse import unquote, urlparse

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
    rabbitmq_url: str = Field(
        default="",
        validation_alias=AliasChoices("RABBITMQ_URL", "CELERY_BROKER_URL"),
    )
    celery_result_backend: str = Field(
        default="",
        validation_alias="CELERY_RESULT_BACKEND",
    )
    celery_task_always_eager: bool = False
    celery_task_soft_time_limit_seconds: int = 900
    celery_task_time_limit_seconds: int = 960
    analysis_task_max_retries: int = 3
    analysis_max_concurrent_per_user: int = 2
    analysis_lease_seconds: int = 900
    analysis_stale_sweep_seconds: int = 300
    payables_reminder_interval_seconds: int = 120
    payables_overdue_interval_seconds: int = 600
    payables_reminder_lookback_days: int = 7
    notifications_delivery_max_retries: int = 3
    notifications_delivery_retry_backoff_seconds: float = 60.0
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "no-reply@paysentineliq.local"
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False
    smtp_timeout_seconds: float = 10.0
    sms_provider: Literal["console"] = "console"
    whatsapp_provider: Literal["console"] = "console"
    metrics_token: str = ""
    otel_sdk_disabled: bool = True
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "paysentineliq-api"
    otel_service_version: str = "0.1.0"
    otel_traces_sampler_ratio: float = 1.0
    otel_exporter_timeout_seconds: float = 5.0
    queue_depth_refresh_seconds: float = 15.0
    rabbitmq_management_url: str = ""
    fraud_model_dir: str = "models/artifacts"
    llm_interpreter: Literal["structured", "crewai"] = "structured"
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
    hybrid_retrieval_enabled: bool = False
    hybrid_fusion: Literal["rrf", "weighted"] = "rrf"
    hybrid_rrf_k: int = 60
    hybrid_dense_weight: float = 0.6
    hybrid_sparse_weight: float = 0.4
    query_embedding_cache_ttl_seconds: int = 3600
    retrieval_model_dir: str = "models/retrieval"
    retrieval_top_k: int = 25
    rerank_top_n: int = 4
    rerank_enabled: bool = True
    embedder_backend: Literal["onnx", "pytorch"] = "onnx"
    reranker_backend: Literal["onnx", "pytorch", "remote"] = "onnx"
    reranker_remote_url: str = ""
    reranker_remote_api_key: str = ""
    reranker_remote_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_timeout_seconds: float = 30.0
    rerank_max_length: int = 512
    batch_size: int = 16
    torch_num_threads: int = 0
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_judge_model: str = ""
    llm_temperature: float = 0.1
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2
    llm_max_output_tokens: int = 800
    llm_max_score_adjustment: int = 5
    llm_language: str = "pt"
    ai_node_timeout_seconds: float = 60.0
    guardrail_classifier_enabled: bool = False
    guardrail_classifier_threshold: float = 0.5
    guardrail_classifier_model_dir: str = "models/artifacts"
    guardrail_judge_enabled: bool = False
    guardrail_max_text_chars: int = 20_000
    guardrail_llm_excerpt_chars: int = 6_000
    guardrail_allowed_output_urls: str = ""

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

    @property
    def guardrail_allowed_output_urls_list(self) -> list[str]:
        return [url.strip() for url in self.guardrail_allowed_output_urls.split(",") if url.strip()]

    @property
    def rabbitmq_management_endpoint(self) -> str:
        if self.rabbitmq_management_url.strip():
            return self.rabbitmq_management_url.strip().rstrip("/")
        parsed = urlparse(self.rabbitmq_url)
        host = parsed.hostname or "localhost"
        return f"http://{host}:15672"

    @property
    def rabbitmq_management_credentials(self) -> tuple[str, str]:
        parsed = urlparse(self.rabbitmq_url)
        return (
            unquote(parsed.username or ""),
            unquote(parsed.password or ""),
        )

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

        if not self.rabbitmq_url:
            if self.app_env == "local":
                self.rabbitmq_url = "amqp://guest:guest@localhost:5672//"
            else:
                missing.append("RABBITMQ_URL")

        if not self.celery_result_backend:
            if self.app_env == "local":
                self.celery_result_backend = "redis://localhost:6379/1"
            else:
                missing.append("CELERY_RESULT_BACKEND")

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
        if self.hybrid_rrf_k <= 0:
            raise ValueError("HYBRID_RRF_K must be positive")
        if self.hybrid_dense_weight < 0 or self.hybrid_sparse_weight < 0:
            raise ValueError("HYBRID_DENSE_WEIGHT and HYBRID_SPARSE_WEIGHT must be non-negative")
        if self.hybrid_dense_weight == 0 and self.hybrid_sparse_weight == 0:
            raise ValueError("at least one hybrid fusion weight must be positive")
        if self.query_embedding_cache_ttl_seconds <= 0:
            raise ValueError("QUERY_EMBEDDING_CACHE_TTL_SECONDS must be positive")
        if not self.retrieval_model_dir.strip():
            raise ValueError("RETRIEVAL_MODEL_DIR must not be empty")
        if self.retrieval_top_k <= 0:
            raise ValueError("RETRIEVAL_TOP_K must be positive")
        if self.rerank_top_n <= 0:
            raise ValueError("RERANK_TOP_N must be positive")
        if self.rerank_top_n > self.retrieval_top_k:
            raise ValueError("RERANK_TOP_N must not exceed RETRIEVAL_TOP_K")
        if self.rerank_max_length <= 0:
            raise ValueError("RERANK_MAX_LENGTH must be positive")
        if self.rerank_timeout_seconds <= 0:
            raise ValueError("RERANK_TIMEOUT_SECONDS must be positive")
        if self.reranker_remote_url and not self.reranker_remote_url.startswith(
            ("http://", "https://"),
        ):
            raise ValueError("RERANKER_REMOTE_URL must start with http:// or https://")
        if self.batch_size <= 0:
            raise ValueError("BATCH_SIZE must be positive")
        if self.torch_num_threads < 0:
            raise ValueError("TORCH_NUM_THREADS must be non-negative")
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
        if not 0.0 <= self.guardrail_classifier_threshold <= 1.0:
            raise ValueError("GUARDRAIL_CLASSIFIER_THRESHOLD must be between 0 and 1")
        if not self.guardrail_classifier_model_dir.strip():
            raise ValueError("GUARDRAIL_CLASSIFIER_MODEL_DIR must not be empty")
        if self.guardrail_judge_enabled and not self.llm_judge_model.strip():
            if self.llm_model.strip():
                self.llm_judge_model = self.llm_model
            else:
                raise ValueError(
                    "LLM_JUDGE_MODEL is required when GUARDRAIL_JUDGE_ENABLED=true",
                )
        if self.guardrail_max_text_chars <= 0:
            raise ValueError("GUARDRAIL_MAX_TEXT_CHARS must be positive")
        if self.guardrail_llm_excerpt_chars <= 0:
            raise ValueError("GUARDRAIL_LLM_EXCERPT_CHARS must be positive")
        if self.guardrail_llm_excerpt_chars > self.guardrail_max_text_chars:
            raise ValueError(
                "GUARDRAIL_LLM_EXCERPT_CHARS must not exceed GUARDRAIL_MAX_TEXT_CHARS",
            )

        if self.celery_task_soft_time_limit_seconds <= 0:
            raise ValueError("CELERY_TASK_SOFT_TIME_LIMIT_SECONDS must be positive")
        if self.celery_task_time_limit_seconds <= self.celery_task_soft_time_limit_seconds:
            raise ValueError(
                "CELERY_TASK_TIME_LIMIT_SECONDS must be greater than "
                "CELERY_TASK_SOFT_TIME_LIMIT_SECONDS",
            )
        if self.analysis_task_max_retries < 0:
            raise ValueError("ANALYSIS_TASK_MAX_RETRIES must be non-negative")
        if self.analysis_max_concurrent_per_user <= 0:
            raise ValueError("ANALYSIS_MAX_CONCURRENT_PER_USER must be positive")
        if self.analysis_lease_seconds <= 0:
            raise ValueError("ANALYSIS_LEASE_SECONDS must be positive")
        if self.analysis_stale_sweep_seconds <= 0:
            raise ValueError("ANALYSIS_STALE_SWEEP_SECONDS must be positive")
        if self.payables_reminder_interval_seconds <= 0:
            raise ValueError("PAYABLES_REMINDER_INTERVAL_SECONDS must be positive")
        if self.payables_overdue_interval_seconds <= 0:
            raise ValueError("PAYABLES_OVERDUE_INTERVAL_SECONDS must be positive")
        if self.payables_reminder_lookback_days < 0:
            raise ValueError("PAYABLES_REMINDER_LOOKBACK_DAYS must be non-negative")
        if self.notifications_delivery_max_retries < 0:
            raise ValueError("NOTIFICATIONS_DELIVERY_MAX_RETRIES must be non-negative")
        if self.notifications_delivery_retry_backoff_seconds <= 0:
            raise ValueError(
                "NOTIFICATIONS_DELIVERY_RETRY_BACKOFF_SECONDS must be positive",
            )
        if not self.smtp_host.strip():
            raise ValueError("SMTP_HOST must not be empty")
        if not 1 <= self.smtp_port <= 65535:
            raise ValueError("SMTP_PORT must be between 1 and 65535")
        if not self.smtp_from.strip():
            raise ValueError("SMTP_FROM must not be empty")
        if self.smtp_timeout_seconds <= 0:
            raise ValueError("SMTP_TIMEOUT_SECONDS must be positive")
        if not self.fraud_model_dir.strip():
            raise ValueError("FRAUD_MODEL_DIR must not be empty")

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

        if not self.metrics_token.strip():
            if self.app_env == "local":
                # Token fixo e publico, valido somente em APP_ENV=local; nao e segredo real.
                self.metrics_token = "local-metrics-token"  # nosec B105
            else:
                missing.append("METRICS_TOKEN")
        elif self.app_env != "local" and self.metrics_token.strip() in {
            "CHANGE_ME",
            "local-metrics-token",
        }:
            raise ValueError("METRICS_TOKEN must be changed outside local")
        if not self.otel_service_name.strip():
            raise ValueError("OTEL_SERVICE_NAME must not be empty")
        if not 0.0 <= self.otel_traces_sampler_ratio <= 1.0:
            raise ValueError("OTEL_TRACES_SAMPLER_RATIO must be between 0 and 1")
        if self.otel_exporter_timeout_seconds <= 0:
            raise ValueError("OTEL_EXPORTER_TIMEOUT_SECONDS must be positive")
        if not self.otel_sdk_disabled:
            endpoint = self.otel_exporter_otlp_endpoint.strip()
            if not endpoint:
                raise ValueError(
                    "OTEL_EXPORTER_OTLP_ENDPOINT is required when OTEL_SDK_DISABLED=false",
                )
            if not endpoint.startswith(("http://", "https://")):
                raise ValueError("OTEL_EXPORTER_OTLP_ENDPOINT must use http or https")
        if self.queue_depth_refresh_seconds <= 0:
            raise ValueError("QUEUE_DEPTH_REFRESH_SECONDS must be positive")

        if missing:
            raise ValueError(f"missing required environment variables: {', '.join(missing)}")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
