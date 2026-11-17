import json
import logging
from collections.abc import Mapping
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

from paysentineliq.application.errors import RerankTimeoutError, RetrievalUnavailableError
from paysentineliq.domain.ports.retrieval import ModelStatus, RerankResult
from paysentineliq.infrastructure.config import Settings
from paysentineliq.infrastructure.retrieval.errors import BGE_RERANKER_MODEL_ID
from paysentineliq.infrastructure.security.ssrf import SafeHttpClient, SSRFGuard

_logger = logging.getLogger("paysentineliq")


class RemoteRerankerHttpClient(Protocol):
    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        content: bytes | None = None,
        allow_internal: bool = False,
    ) -> httpx.Response: ...


class _RemoteRerankResult(BaseModel):
    index: int
    score: float


class _RemoteRerankResponse(BaseModel):
    results: list[_RemoteRerankResult]


class RemoteReranker:
    def __init__(
        self,
        settings: Settings,
        *,
        client: RemoteRerankerHttpClient | None = None,
    ) -> None:
        self._url = settings.reranker_remote_url.strip()
        self._api_key = settings.reranker_remote_api_key.strip()
        self._model_id = settings.reranker_remote_model.strip() or BGE_RERANKER_MODEL_ID
        self._max_length = settings.rerank_max_length
        self._allow_internal = settings.app_env == "local"
        if client is not None:
            self._client = client
        else:
            guard = SSRFGuard(
                require_https=settings.app_env != "local",
                allowed_hosts=set(settings.ssrf_allowed_hosts_list),
            )
            self._client = SafeHttpClient(
                guard,
                timeout=httpx.Timeout(
                    settings.rerank_timeout_seconds,
                    connect=min(3.0, settings.rerank_timeout_seconds),
                ),
            )

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def backend(self) -> str:
        return "remote"

    @property
    def status(self) -> ModelStatus:
        loaded = bool(self._url)
        return ModelStatus(
            model_id=self._model_id,
            backend="remote",
            loaded=loaded,
            error=None if loaded else "remote_not_configured",
        )

    def load(self) -> None:
        return None

    async def rerank(
        self,
        query: str,
        documents: tuple[str, ...],
        *,
        top_n: int | None = None,
    ) -> tuple[RerankResult, ...]:
        if not query.strip():
            raise ValueError("query is required")
        if top_n is not None and top_n <= 0:
            raise ValueError("top_n must be positive")
        if not documents:
            return ()
        if not self._url:
            raise RetrievalUnavailableError("remote_not_configured")

        limit = min(top_n or len(documents), len(documents))
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self._model_id,
            "query": query,
            "documents": list(documents),
            "top_n": limit,
            "max_length": self._max_length,
        }
        try:
            response = await self._client.request(
                "POST",
                self._url,
                headers=headers,
                content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                allow_internal=self._allow_internal,
            )
        except httpx.TimeoutException as exc:
            _logger.warning("remote_reranker_timeout")
            raise RerankTimeoutError("remote reranker timed out") from exc
        except Exception as exc:
            _logger.warning("remote_reranker_request_failed")
            raise RetrievalUnavailableError("remote reranker request failed") from exc

        if response.status_code < 200 or response.status_code >= 300:
            _logger.warning(
                "remote_reranker_http_error status=%s",
                response.status_code,
            )
            raise RetrievalUnavailableError("remote reranker http error")
        try:
            parsed = _RemoteRerankResponse.model_validate_json(response.content)
        except (ValidationError, ValueError) as exc:
            _logger.warning("remote_reranker_invalid_response")
            raise RetrievalUnavailableError("remote reranker invalid response") from exc

        indices = [item.index for item in parsed.results]
        if len(set(indices)) != len(indices) or any(
            index < 0 or index >= len(documents) for index in indices
        ):
            raise RetrievalUnavailableError("remote reranker invalid indices")
        try:
            results = [RerankResult(index=item.index, score=item.score) for item in parsed.results]
        except ValueError as exc:
            raise RetrievalUnavailableError("remote reranker invalid scores") from exc
        results.sort(key=lambda item: (-item.score, item.index))
        return tuple(results[:limit])

    async def aclose(self) -> None:
        return None
