import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from paysentineliq.application.commands.process_analysis import ProcessAnalysisHandler
from paysentineliq.application.errors import StorageNotConfiguredError
from paysentineliq.application.ports.embedding import EmbeddingPort
from paysentineliq.application.ports.hybrid_vector_store import HybridVectorStorePort
from paysentineliq.application.ports.interpretation import EvidenceInterpreterPort
from paysentineliq.application.ports.rag import RagContextPort
from paysentineliq.application.ports.vector_store import VectorStorePort
from paysentineliq.application.queries.fraud_scoring import FraudScoringService
from paysentineliq.application.queries.hybrid_retrieval import HybridRetriever
from paysentineliq.application.queries.knowledge_retrieval import KnowledgeRetriever
from paysentineliq.application.queries.two_stage_retrieval import TwoStageRetriever
from paysentineliq.infrastructure.ai.crew import CrewAIInterpreter
from paysentineliq.infrastructure.ai.graph import LangGraphAnalysisOrchestrator
from paysentineliq.infrastructure.ai.judge import LlmReportJudge
from paysentineliq.infrastructure.ai.llm import OpenAICompatibleLLM
from paysentineliq.infrastructure.ai.prompts import PromptRepository
from paysentineliq.infrastructure.ai.structured import StructuredInterpreter
from paysentineliq.infrastructure.ai.unavailable import (
    UnavailableInterpreter,
    UnavailableRetriever,
)
from paysentineliq.infrastructure.cache.embedding_cache import CachedEmbedder
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.db.repositories.analyses import (
    SqlAlchemyAnalysisEventRepository,
    SqlAlchemyAnalysisRepository,
    SqlAlchemyNotificationRepository,
)
from paysentineliq.infrastructure.db.repositories.analysis_documents import (
    SqlAlchemyAnalysisDocumentAdapter,
)
from paysentineliq.infrastructure.ingestion.service import DocumentIngestionService
from paysentineliq.infrastructure.metrics.guardrails import InMemoryGuardrailMetrics
from paysentineliq.infrastructure.ml.artifact import load_fraud_model_or_none
from paysentineliq.infrastructure.observability.metrics import get_platform_metrics
from paysentineliq.infrastructure.observability.tracing import (
    instrument_sqlalchemy_engine,
)
from paysentineliq.infrastructure.ocr.paddle import PaddleOcrAdapter
from paysentineliq.infrastructure.rag.embeddings import OpenAICompatibleEmbedding
from paysentineliq.infrastructure.rag.fake_embedding import DeterministicHashEmbedding
from paysentineliq.infrastructure.rag.pgvector import PGVectorStore
from paysentineliq.infrastructure.rag.pgvector_hybrid import PGVectorHybridStore
from paysentineliq.infrastructure.rag.pinecone import PineconeVectorStore
from paysentineliq.infrastructure.rag.pinecone_hybrid import PineconeHybridVectorStore
from paysentineliq.infrastructure.retrieval.runtime import RetrievalRuntime
from paysentineliq.infrastructure.security.ssrf import SafeHttpClient, SSRFGuard
from paysentineliq.infrastructure.storage.s3 import S3StorageAdapter
from paysentineliq.infrastructure.vision.visual_anomalies import VisualAnomalyService

_logger = logging.getLogger("paysentineliq")


def build_analysis_orchestrator(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    storage: S3StorageAdapter,
    *,
    retrieval_runtime: RetrievalRuntime | None = None,
    redis: Redis | None = None,
) -> LangGraphAnalysisOrchestrator:
    prompts = PromptRepository()
    guard = SSRFGuard(
        require_https=settings.app_env != "local",
        allowed_hosts=set(settings.ssrf_allowed_hosts_list),
    )
    http_client = SafeHttpClient(guard)
    interpreter = _build_interpreter(settings, prompts, guard)
    judge = _build_judge(settings, prompts, http_client)
    ingestion = DocumentIngestionService(
        PaddleOcrAdapter(languages=tuple(settings.ocr_languages_list)),
        VisualAnomalyService(),
        languages=tuple(settings.ocr_languages_list),
        max_pages=settings.ocr_max_pages,
        render_dpi=settings.ocr_render_dpi,
        timeout_seconds=settings.ocr_timeout_seconds,
        max_image_pixels=settings.ocr_max_image_pixels,
        native_min_chars=settings.ocr_native_min_chars,
    )
    return LangGraphAnalysisOrchestrator(
        ingestion=ingestion,
        fraud_service=FraudScoringService(
            model=load_fraud_model_or_none(Path(settings.fraud_model_dir)),
        ),
        retriever=_build_retriever(
            settings,
            session_factory,
            retrieval_runtime=retrieval_runtime,
            redis=redis,
        ),
        interpreter=interpreter,
        analyses=SqlAlchemyAnalysisRepository(session_factory),
        events=SqlAlchemyAnalysisEventRepository(session_factory),
        storage=storage,
        settings=settings,
        judge=judge,
        metrics=InMemoryGuardrailMetrics(),
    )


@asynccontextmanager
async def build_worker_runtime(
    settings: Settings,
) -> AsyncIterator[ProcessAnalysisHandler]:
    if not settings.s3_configured:
        raise StorageNotConfiguredError()
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    instrument_sqlalchemy_engine(engine.sync_engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    retrieval_runtime: RetrievalRuntime | None = None
    cache_redis: Redis | None = None
    if settings.hybrid_retrieval_enabled:
        retrieval_runtime = RetrievalRuntime(settings)
        await retrieval_runtime.load()
        cache_redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        storage = S3StorageAdapter(settings)
        orchestrator = build_analysis_orchestrator(
            settings,
            session_factory,
            storage,
            retrieval_runtime=retrieval_runtime,
            redis=cache_redis,
        )
        yield ProcessAnalysisHandler(
            SqlAlchemyAnalysisDocumentAdapter(session_factory, storage),
            orchestrator,
            SqlAlchemyAnalysisRepository(session_factory),
            SqlAlchemyNotificationRepository(session_factory),
            lease_seconds=settings.analysis_lease_seconds,
        )
    finally:
        if retrieval_runtime is not None:
            await retrieval_runtime.aclose()
        if cache_redis is not None:
            await cache_redis.aclose()
        await engine.dispose()


def _build_interpreter(
    settings: Settings,
    prompts: PromptRepository,
    guard: SSRFGuard,
) -> EvidenceInterpreterPort:
    if not settings.llm_base_url.strip() or not settings.llm_model.strip():
        return UnavailableInterpreter()
    if settings.llm_interpreter == "crewai":
        return CrewAIInterpreter(
            settings=settings,
            prompts=prompts,
            guard=guard,
            timeout_seconds=settings.ai_node_timeout_seconds,
        )
    llm = OpenAICompatibleLLM(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        temperature=settings.llm_temperature,
        max_retries=settings.llm_max_retries,
        timeout_seconds=settings.llm_timeout_seconds,
        client=SafeHttpClient(guard),
    )
    return StructuredInterpreter(
        llm,
        prompts,
        timeout_seconds=settings.ai_node_timeout_seconds,
        max_document_chars=settings.guardrail_llm_excerpt_chars,
    )


def _build_judge(
    settings: Settings,
    prompts: PromptRepository,
    client: SafeHttpClient,
) -> LlmReportJudge | None:
    if not settings.guardrail_judge_enabled:
        return None
    model = settings.llm_judge_model or settings.llm_model
    if not settings.llm_base_url.strip() or not model.strip():
        return None
    llm = OpenAICompatibleLLM(
        base_url=settings.llm_base_url,
        model=model,
        api_key=settings.llm_api_key,
        temperature=0.0,
        max_retries=settings.llm_max_retries,
        timeout_seconds=settings.llm_timeout_seconds,
        client=client,
    )
    return LlmReportJudge(
        llm,
        prompts,
        timeout_seconds=settings.ai_node_timeout_seconds,
    )


def _build_retriever(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    retrieval_runtime: RetrievalRuntime | None = None,
    redis: Redis | None = None,
) -> RagContextPort:
    if settings.hybrid_retrieval_enabled:
        return _build_hybrid_retriever(
            settings,
            session_factory,
            retrieval_runtime=retrieval_runtime,
            redis=redis,
        )
    fake = settings.rag_fake_embedder or not (
        settings.embedding_base_url.strip() and settings.embedding_model.strip()
    )
    dimension = settings.embedding_dim
    if fake:
        dimension = dimension if dimension > 0 else 8
        embedder: EmbeddingPort = DeterministicHashEmbedding(dimension=dimension)
    else:
        if dimension <= 0:
            return UnavailableRetriever()
        embedder = OpenAICompatibleEmbedding(
            base_url=settings.embedding_base_url,
            model=settings.embedding_model,
            dimension=dimension,
            api_key=settings.embedding_api_key,
            timeout_seconds=settings.embedding_timeout_seconds,
            batch_size=settings.embedding_batch_size,
            max_retries=settings.embedding_max_retries,
            backoff_seconds=settings.embedding_retry_backoff_seconds,
        )
    try:
        if settings.vector_store == "pinecone":
            store: VectorStorePort = PineconeVectorStore.from_settings(settings)
        else:
            store = PGVectorStore(session_factory, dimension=dimension)
    except Exception:
        return UnavailableRetriever()
    return KnowledgeRetriever(embedder, store)


def _build_hybrid_retriever(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    retrieval_runtime: RetrievalRuntime | None,
    redis: Redis | None,
) -> RagContextPort:
    if retrieval_runtime is None or redis is None:
        return UnavailableRetriever()
    embedder = retrieval_runtime.embedder
    if not embedder.status.loaded or not embedder.sparse_status.loaded:
        _logger.warning("hybrid_retrieval_models_unavailable")
        return UnavailableRetriever()
    cached = CachedEmbedder(
        embedder,
        retrieval_runtime.sparse_embedder,
        redis,
        ttl_seconds=settings.query_embedding_cache_ttl_seconds,
    )
    try:
        if settings.vector_store == "pinecone":
            store: HybridVectorStorePort = PineconeHybridVectorStore.from_settings(settings)
        else:
            store = PGVectorHybridStore(session_factory)
    except Exception:
        _logger.warning("hybrid_retrieval_store_unavailable")
        return UnavailableRetriever()
    platform_metrics = get_platform_metrics()
    stage1 = HybridRetriever(
        cached,
        cached,
        store,
        hybrid_embedder=cached,
        default_limit=settings.retrieval_top_k,
        fusion=settings.hybrid_fusion,
        rrf_k=settings.hybrid_rrf_k,
        dense_weight=settings.hybrid_dense_weight,
        sparse_weight=settings.hybrid_sparse_weight,
        metrics=platform_metrics,
    )
    reranker = retrieval_runtime.reranker if settings.rerank_enabled else None
    if reranker is not None and not reranker.status.loaded:
        reranker = None
    return TwoStageRetriever(
        stage1,
        reranker=reranker,
        rerank_enabled=settings.rerank_enabled,
        top_n=settings.rerank_top_n,
        timeout_seconds=settings.rerank_timeout_seconds,
        metrics=platform_metrics,
    )
