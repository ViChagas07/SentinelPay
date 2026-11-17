import pytest

from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.retrieval.runtime import RetrievalRuntime
from tests.support.retrieval_fakes import FakeEmbedder, FakeReranker

pytestmark = pytest.mark.unit


async def test_runtime_loads_models_only_once() -> None:
    embedder = FakeEmbedder()
    reranker = FakeReranker()
    runtime = RetrievalRuntime(
        Settings(app_env="local"),
        embedder=embedder,
        reranker=reranker,
    )

    await runtime.load()
    await runtime.load()

    assert embedder.loads == 1
    assert reranker.loads == 1
    assert runtime.load_attempted is True
    assert runtime.status.embedder.loaded is True
    assert runtime.status.reranker is not None
    assert runtime.status.reranker.loaded is True


async def test_runtime_skips_reranker_when_disabled() -> None:
    embedder = FakeEmbedder()
    reranker = FakeReranker()
    runtime = RetrievalRuntime(
        Settings(app_env="local", rerank_enabled=False),
        embedder=embedder,
        reranker=reranker,
    )

    await runtime.load()

    assert embedder.loads == 1
    assert reranker.loads == 0
    assert runtime.status.rerank_enabled is False
    assert runtime.status.reranker is None


async def test_runtime_exposes_load_error_without_raising() -> None:
    embedder = FakeEmbedder(error="model_files_missing")
    runtime = RetrievalRuntime(
        Settings(app_env="local", rerank_enabled=False),
        embedder=embedder,
    )

    await runtime.load()

    assert runtime.status.embedder.loaded is False
    assert runtime.status.embedder.error == "model_files_missing"
    assert runtime.status.sparse_embedder.error == "model_files_missing"


async def test_runtime_builds_remote_reranker_from_settings() -> None:
    settings = Settings(
        app_env="local",
        reranker_backend="remote",
        reranker_remote_url="https://reranker.example/v1/rerank",
    )
    runtime = RetrievalRuntime(settings, embedder=FakeEmbedder())

    await runtime.load()

    assert runtime.status.reranker is not None
    assert runtime.status.reranker.backend == "remote"
    assert runtime.status.reranker.loaded is True


async def test_runtime_reports_unconfigured_remote_reranker() -> None:
    settings = Settings(
        app_env="local",
        reranker_backend="remote",
        reranker_remote_url="",
    )
    runtime = RetrievalRuntime(settings, embedder=FakeEmbedder())

    await runtime.load()

    assert runtime.status.reranker is not None
    assert runtime.status.reranker.loaded is False
    assert runtime.status.reranker.error == "remote_not_configured"


async def test_runtime_close_is_idempotent() -> None:
    embedder = FakeEmbedder()
    runtime = RetrievalRuntime(
        Settings(app_env="local", rerank_enabled=False),
        embedder=embedder,
    )

    await runtime.aclose()
    await runtime.aclose()

    assert embedder.closes == 1
