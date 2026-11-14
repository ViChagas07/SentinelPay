from typing import Protocol

from paysentineliq.application.queries.knowledge_retrieval import (
    KnowledgeQuery,
    KnowledgeRetrievalResult,
)


class RagContextPort(Protocol):
    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeRetrievalResult: ...
