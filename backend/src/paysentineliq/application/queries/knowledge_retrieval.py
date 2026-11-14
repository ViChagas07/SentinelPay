import logging
from dataclasses import dataclass
from datetime import date

from paysentineliq.application.errors import EmbeddingDimensionError
from paysentineliq.application.ports.embedding import EmbeddingPort
from paysentineliq.application.ports.vector_store import VectorStorePort
from paysentineliq.domain.knowledge import KnowledgeFilter, Provenance

_logger = logging.getLogger("paysentineliq")


@dataclass(frozen=True, slots=True)
class KnowledgeQuery:
    text: str
    categories: tuple[str, ...] = ()
    as_of: date | None = None
    limit: int = 5

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("query text is required")
        if self.limit <= 0:
            raise ValueError("limit must be positive")


@dataclass(frozen=True, slots=True)
class KnowledgeCitation:
    document_key: str
    path: str
    title: str
    category: str
    section: str
    provenance: Provenance
    source: str
    version: str | None
    authoritative: bool


@dataclass(frozen=True, slots=True)
class RetrievedPassage:
    content: str
    citation: KnowledgeCitation
    score: float


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalResult:
    passages: tuple[RetrievedPassage, ...]
    rag_unavailable: bool
    reason: str | None


class KnowledgeRetriever:
    def __init__(
        self,
        embedder: EmbeddingPort,
        store: VectorStorePort,
        *,
        default_limit: int = 5,
    ) -> None:
        if default_limit <= 0:
            raise ValueError("default_limit must be positive")
        self._embedder = embedder
        self._store = store
        self._default_limit = default_limit

    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeRetrievalResult:
        try:
            vectors = await self._embedder.embed((query.text,))
            if not vectors:
                raise EmbeddingDimensionError("embedding was not produced")
            vector = vectors[0]
            if len(vector) != self._embedder.dimension:
                raise EmbeddingDimensionError("embedding dimension mismatch")
            filters = KnowledgeFilter(
                categories=query.categories,
                as_of=query.as_of or date.today(),
            )
            rows = await self._store.query(
                vector,
                limit=query.limit or self._default_limit,
                filters=filters,
            )
            passages = tuple(
                RetrievedPassage(
                    content=row.content,
                    citation=KnowledgeCitation(
                        document_key=row.document_key,
                        path=row.path,
                        title=row.title,
                        category=row.category,
                        section=row.section,
                        provenance=row.provenance,
                        source=row.source,
                        version=row.version,
                        authoritative=row.authoritative,
                    ),
                    score=row.score,
                )
                for row in rows
            )
            return KnowledgeRetrievalResult(
                passages=passages,
                rag_unavailable=False,
                reason=None,
            )
        except Exception:
            _logger.error("rag_unavailable")
            return KnowledgeRetrievalResult(
                passages=(),
                rag_unavailable=True,
                reason="rag_unavailable",
            )
