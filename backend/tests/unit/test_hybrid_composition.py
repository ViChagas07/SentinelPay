from types import SimpleNamespace
from typing import cast

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paysentineliq.application.queries.hybrid_retrieval import HybridRetriever
from paysentineliq.application.queries.two_stage_retrieval import TwoStageRetriever
from paysentineliq.infrastructure.ai.unavailable import UnavailableRetriever
from paysentineliq.infrastructure.composition import analysis_worker
from paysentineliq.infrastructure.composition.analysis_worker import _build_retriever
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.retrieval.runtime import RetrievalRuntime
from tests.support.retrieval_fakes import FakeEmbedder

pytestmark = pytest.mark.unit


class DummyHybridStore:
    async def upsert_hybrid_document(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("not used")

    async def delete_document(self, document_key: str) -> None:
        raise AssertionError("not used")

    async def dense_query(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("not used")

    async def sparse_query(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("not used")


def _session_factory() -> async_sessionmaker[AsyncSession]:
    return cast(async_sessionmaker[AsyncSession], object())


def test_hybrid_flag_builds_hybrid_retriever(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedder = FakeEmbedder()
    embedder.load()
    runtime = cast(
        RetrievalRuntime,
        SimpleNamespace(
            embedder=embedder,
            sparse_embedder=embedder,
            reranker=None,
        ),
    )
    monkeypatch.setattr(
        analysis_worker,
        "PGVectorHybridStore",
        lambda factory: DummyHybridStore(),
    )
    settings = Settings(app_env="local", hybrid_retrieval_enabled=True)

    retriever = _build_retriever(
        settings,
        _session_factory(),
        retrieval_runtime=runtime,
        redis=cast(Redis, object()),
    )

    assert isinstance(retriever, TwoStageRetriever)


def test_hybrid_flag_degrades_when_models_are_not_loaded() -> None:
    embedder = FakeEmbedder()
    runtime = cast(
        RetrievalRuntime,
        SimpleNamespace(
            embedder=embedder,
            sparse_embedder=embedder,
            reranker=None,
        ),
    )
    settings = Settings(app_env="local", hybrid_retrieval_enabled=True)

    retriever = _build_retriever(
        settings,
        _session_factory(),
        retrieval_runtime=runtime,
        redis=cast(Redis, object()),
    )

    assert isinstance(retriever, UnavailableRetriever)


def test_hybrid_flag_off_keeps_old_retriever() -> None:
    settings = Settings(app_env="local", rag_fake_embedder=True)

    retriever = _build_retriever(settings, _session_factory())

    assert not isinstance(retriever, HybridRetriever)
    assert not isinstance(retriever, TwoStageRetriever)
