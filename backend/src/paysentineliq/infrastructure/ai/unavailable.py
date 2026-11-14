from paysentineliq.application.errors import LlmUnavailableError, RagUnavailableError
from paysentineliq.application.ports.interpretation import (
    InterpretationRequest,
    InterpretationResult,
)
from paysentineliq.application.queries.knowledge_retrieval import (
    KnowledgeQuery,
    KnowledgeRetrievalResult,
)


class UnavailableInterpreter:
    async def interpret(self, request: InterpretationRequest) -> InterpretationResult:
        raise LlmUnavailableError("LLM is not configured")


class UnavailableRetriever:
    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeRetrievalResult:
        raise RagUnavailableError("RAG is not configured")
