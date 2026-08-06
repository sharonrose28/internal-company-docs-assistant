from time import monotonic

import structlog

from app.core.config import Settings
from app.models.chat import ChatMessage
from app.models.user import User
from app.repositories.chat import ChatRepository
from app.repositories.document import DocumentRepository
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.search import SearchMode
from app.services.audit import AuditService
from app.services.cache import CacheService
from app.services.citations import CitationService, InvalidCitationError
from app.services.context import ContextBuilder
from app.services.generation import AnswerGenerator
from app.services.memory import ConversationMemoryService
from app.services.retrieval import RetrievalService
from app.core.metrics import QUERIES

logger = structlog.get_logger()
REFUSAL = "I couldn't find enough trusted information in the documents available to you."


class RAGService:
    """Permission-gated RAG orchestration. Retrieved text never bypasses authorization."""

    def __init__(
        self,
        settings: Settings,
        retrieval: RetrievalService,
        documents: DocumentRepository,
        chats: ChatRepository,
        generator: AnswerGenerator,
        audit: AuditService,
        memory: ConversationMemoryService,
        context_builder: ContextBuilder | None = None,
        citations: CitationService | None = None,
        cache: CacheService | None = None,
    ):
        self.settings = settings
        self.retrieval = retrieval
        self.documents = documents
        self.chats = chats
        self.generator = generator
        self.audit = audit
        self.memory = memory
        self.context_builder = context_builder or ContextBuilder(settings.rag_context_tokens)
        self.citations = citations or CitationService()
        self.cache = cache

    async def ask(self, request: ChatRequest, user: User) -> ChatResponse:
        started = monotonic()
        results = []
        try:
            memory = await self.memory.load(user, request.session_id, request.question)
            session_id = memory.session.id
            generation = await self.cache.generation() if self.cache else 0
            answer_key = self.cache.answer_key(
                generation, user, request.question, memory.fingerprint
            ) if self.cache else None
            if self.cache and answer_key:
                cached = await self.cache.get_json(answer_key)
                if cached:
                    cached_response = ChatResponse.model_validate(cached)
                    document_ids = {citation.document_id for citation in cached_response.citations}
                    authorized = await self.documents.authorized_document_ids(user, document_ids)
                    if authorized == document_ids:
                        await self._store_message(request, user, session_id, cached_response)
                        await self.audit.record(
                            user_id=user.id,
                            question=request.question,
                            outcome="answer_cache_hit",
                            document_ids=[str(value) for value in document_ids],
                            chunk_ids=[],
                            model=self.settings.rag_model,
                            latency_ms=round((monotonic() - started) * 1000, 2),
                            details={"cache": "answer"},
                        )
                        return cached_response
                    await self.cache.delete(answer_key)
            # Retrieval applies Qdrant filters before candidates are returned and verifies IDs in PostgreSQL.
            retrieval_query = self.memory.retrieval_query(request.question, memory)
            results = await self.retrieval.search(
                retrieval_query,
                user,
                self.documents,
                SearchMode.HYBRID,
            )
            if not results:
                return await self._refuse(
                    request, user, session_id, started, "no_authorized_evidence", results
                )

            threshold = self.settings.rag_hybrid_score_threshold
            trusted_results = [result for result in results if result.score >= threshold]
            if not trusted_results:
                return await self._refuse(
                    request, user, session_id, started, "below_similarity_threshold", results
                )

            context = self.context_builder.build(trusted_results)
            if not context.sources:
                return await self._refuse(
                    request, user, session_id, started, "empty_context", trusted_results
                )

            generated = await self.generator.generate(
                request.question, context, self.memory.prompt_context(memory)
            )
            if generated.contradictory:
                return await self._refuse(
                    request, user, session_id, started, "contradictory_evidence", trusted_results
                )
            if not generated.supported:
                return await self._refuse(
                    request, user, session_id, started, "requested_information_missing", trusted_results
                )
            try:
                citation_models = self.citations.build(generated, context)
            except InvalidCitationError:
                logger.warning("rag_invalid_citations", user_id=str(user.id))
                return await self._refuse(
                    request, user, session_id, started, "invalid_citations", trusted_results
                )

            if (
                generated.confidence < self.settings.rag_min_confidence
                or not citation_models
            ):
                return await self._refuse(
                    request, user, session_id, started, "insufficient_evidence", trusted_results
                )

            response = ChatResponse(
                session_id=session_id,
                answer=self.citations.render_answer(generated.answer, citation_models),
                status="answered",
                confidence=generated.confidence,
                citations=citation_models,
            )
            await self._store_message(request, user, session_id, response)
            await self._audit(
                request, user, started, "answered", trusted_results,
                [citation.source_id for citation in citation_models],
            )
            if self.cache and answer_key:
                await self.cache.set_json(answer_key, response.model_dump(mode="json"))
            return response
        except Exception as exc:
            logger.exception(
                "rag_pipeline_failed",
                user_id=str(user.id),
                retrieved_count=len(results),
                error_type=type(exc).__name__,
            )
            try:
                await self._audit(
                    request, user, started, "failed", results, [],
                    {"error_type": type(exc).__name__},
                )
            except Exception:
                logger.exception("rag_failure_audit_failed", user_id=str(user.id))
            raise

    async def _refuse(self, request, user, session_id, started, outcome, results) -> ChatResponse:
        response = ChatResponse(
            session_id=session_id,
            answer=REFUSAL,
            status="insufficient_evidence",
            confidence=0.0,
            citations=[],
        )
        await self._store_message(request, user, session_id, response)
        await self._audit(request, user, started, outcome, results, [])
        return response

    async def _store_message(self, request, user, session_id, response) -> None:
        await self.chats.add(ChatMessage(
            user_id=user.id,
            session_id=session_id,
            question=request.question,
            answer=response.answer or REFUSAL,
            confidence=response.confidence,
            citations=[citation.model_dump(mode="json") for citation in response.citations],
        ))

    async def _audit(self, request, user, started, outcome, results, citation_ids, details=None) -> None:
        latency_ms = round((monotonic() - started) * 1000, 2)
        QUERIES.labels(outcome).inc()
        await self.audit.record(
            user_id=user.id,
            question=request.question,
            outcome=outcome,
            document_ids=list(dict.fromkeys(str(result.document_id) for result in results)),
            chunk_ids=[
                str(result.metadata["chunk_id"])
                for index, result in enumerate(results, start=1)
                if f"S{index}" in citation_ids and result.metadata.get("chunk_id")
            ],
            model=self.settings.rag_model if outcome == "answered" else None,
            latency_ms=latency_ms,
            details={"retrieved_count": len(results), **(details or {})},
        )
        logger.info(
            "rag_pipeline_completed",
            user_id=str(user.id),
            outcome=outcome,
            retrieved_count=len(results),
            citation_count=len(citation_ids),
            latency_ms=latency_ms,
        )
