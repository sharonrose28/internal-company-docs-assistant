import asyncio
import logging
from time import monotonic

from langchain_openai import OpenAIEmbeddings
from qdrant_client import AsyncQdrantClient, models as qmodels

from app.core.config import Settings
from app.core.exceptions import ForbiddenError
from app.models.user import Role, User
from app.repositories.document import DocumentRepository
from app.schemas.search import SearchFilters, SearchMode, SearchResult
from app.services.cache import CacheService
from app.services.embedding import EmbeddingConfigurationError
from app.core.metrics import OPERATION_LATENCY

logger = logging.getLogger("app.retrieval")
TOP_K = 5


class RetrievalService:
    def __init__(
        self, settings: Settings, dense_embeddings=None, sparse_embeddings=None,
        qdrant=None, cache: CacheService | None = None,
    ):
        if dense_embeddings is None and (
            not settings.openai_api_key or not settings.openai_api_key.get_secret_value()
        ):
            raise EmbeddingConfigurationError("OPENAI_API_KEY is required for semantic retrieval")
        self.settings = settings
        self.dense = dense_embeddings or OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.openai_api_key.get_secret_value(),
            max_retries=settings.embedding_max_retries,
            request_timeout=30,
        )
        if sparse_embeddings is None:
            # Avoid loading ONNX Runtime while FastAPI imports its routers. It is
            # only required once a retrieval request constructs this service.
            from fastembed import SparseTextEmbedding

            sparse_embeddings = SparseTextEmbedding(model_name="Qdrant/bm25")
        self.sparse = sparse_embeddings
        self.qdrant = qdrant or AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
            timeout=10,
        )
        self.cache = cache

    async def search(
        self,
        query: str,
        user: User,
        authorizer: DocumentRepository,
        mode: SearchMode = SearchMode.HYBRID,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        started = monotonic()
        filters = filters or SearchFilters()
        if filters.document_id:
            authorized = await authorizer.authorized_document_ids(user, {filters.document_id})
            if filters.document_id not in authorized:
                raise ForbiddenError("You are not authorized to search this document")
        # A new installation has no collection until its first document is embedded.
        # Treat that valid empty state as no evidence, not as an infrastructure failure.
        if not await self.qdrant.collection_exists(self.settings.qdrant_collection):
            logger.info("vector_collection_empty", extra={"collection": self.settings.qdrant_collection})
            OPERATION_LATENCY.labels("retrieval", "empty").observe(monotonic() - started)
            return []
        generation = await self.cache.generation() if self.cache else 0
        cache_key = self.cache.retrieval_key(
            generation, user, query, mode.value, filters.model_dump(mode="json")
        ) if self.cache else None
        if self.cache and cache_key:
            cached = await self.cache.get_json(cache_key)
            if isinstance(cached, list):
                cached_results = [SearchResult.model_validate(item) for item in cached]
                cached_ids = {result.document_id for result in cached_results}
                authorized_ids = await authorizer.authorized_document_ids(user, cached_ids)
                if authorized_ids == cached_ids:
                    logger.info(
                        "vector_search_cache_hit",
                        extra={"mode": mode.value, "result_count": len(cached_results)},
                    )
                    return cached_results[:TOP_K]
                await self.cache.delete(cache_key)
        query_filter = self._build_filter(user, filters)
        embedding_key = self.cache.embedding_key(
            query, self.settings.embedding_model, mode.value
        ) if self.cache else None
        cached_vectors = await self.cache.get_json(embedding_key) if self.cache and embedding_key else None
        if not isinstance(cached_vectors, dict) or "dense" not in cached_vectors:
            cached_vectors = None
        elif mode == SearchMode.HYBRID and not {
            "sparse_indices", "sparse_values"
        }.issubset(cached_vectors):
            cached_vectors = None
        embedding_started = monotonic()
        dense_task = None if cached_vectors else asyncio.create_task(self.dense.aembed_query(query))
        qdrant_started = monotonic()

        if mode == SearchMode.HYBRID:
            if cached_vectors:
                dense_vector = cached_vectors["dense"]
                sparse_vector = qmodels.SparseVector(
                    indices=cached_vectors["sparse_indices"],
                    values=cached_vectors["sparse_values"],
                )
            else:
                sparse_task = asyncio.create_task(asyncio.to_thread(self._sparse_query, query))
                dense_vector, sparse_vector = await asyncio.gather(dense_task, sparse_task)
                if self.cache and embedding_key:
                    await self.cache.set_json(embedding_key, {
                        "dense": dense_vector,
                        "sparse_indices": sparse_vector.indices,
                        "sparse_values": sparse_vector.values,
                    })
            response = await self.qdrant.query_points(
                collection_name=self.settings.qdrant_collection,
                prefetch=[
                    qmodels.Prefetch(
                        query=dense_vector,
                        using="dense",
                        filter=query_filter,
                        limit=self.settings.retrieval_candidate_limit,
                        params=qmodels.SearchParams(hnsw_ef=64, exact=False),
                    ),
                    qmodels.Prefetch(
                        query=sparse_vector,
                        using="bm25",
                        filter=query_filter,
                        limit=self.settings.retrieval_candidate_limit,
                    ),
                ],
                query=qmodels.FusionQuery(fusion=qmodels.Fusion.RRF),
                limit=TOP_K,
                with_payload=True,
                with_vectors=False,
            )
        else:
            dense_vector = cached_vectors["dense"] if cached_vectors else await dense_task
            if self.cache and embedding_key and not cached_vectors:
                await self.cache.set_json(embedding_key, {"dense": dense_vector})
            response = await self.qdrant.query_points(
                collection_name=self.settings.qdrant_collection,
                query=dense_vector,
                using="dense",
                query_filter=query_filter,
                search_params=qmodels.SearchParams(hnsw_ef=64, exact=False),
                limit=TOP_K,
                with_payload=True,
                with_vectors=False,
            )

        qdrant_elapsed = monotonic() - qdrant_started
        OPERATION_LATENCY.labels("qdrant_search", "success").observe(qdrant_elapsed)
        if not cached_vectors:
            OPERATION_LATENCY.labels("query_embedding", "success").observe(
                qdrant_started - embedding_started
            )
        logger.info(
            "qdrant_search_completed",
            extra={"mode": mode.value, "latency_ms": round(qdrant_elapsed * 1000, 2)},
        )
        candidates = [self._result(point) for point in response.points]
        authorized_ids = await authorizer.authorized_document_ids(
            user, {result.document_id for result in candidates}
        )
        results = [result for result in candidates if result.document_id in authorized_ids][:TOP_K]
        if self.cache and cache_key:
            await self.cache.set_json(
                cache_key, [result.model_dump(mode="json") for result in results]
            )
        total_elapsed = monotonic() - started
        OPERATION_LATENCY.labels("retrieval", "success").observe(total_elapsed)
        logger.info("vector_search_completed", extra={
            "mode": mode.value,
            "result_count": len(results),
            "top_k": TOP_K,
            "latency_ms": round(total_elapsed * 1000, 2),
            "department_filter": str(filters.department_id) if filters.department_id else None,
            "document_filter": str(filters.document_id) if filters.document_id else None,
        })
        return results

    def _sparse_query(self, query: str) -> qmodels.SparseVector:
        sparse = next(iter(self.sparse.query_embed(query)))
        return qmodels.SparseVector(
            indices=sparse.indices.tolist(),
            values=sparse.values.tolist(),
        )

    @staticmethod
    def _build_filter(user: User, filters: SearchFilters) -> qmodels.Filter | None:
        must: list = []
        if user.role == Role.MANAGER:
            if filters.department_id and filters.department_id != user.department_id:
                raise ForbiddenError("The requested department is outside your access scope")
            if not user.department_id:
                raise ForbiddenError("Manager account has no department scope")
            must.append(
                qmodels.FieldCondition(
                    key="department", match=qmodels.MatchValue(value=str(user.department_id))
                )
            )
        elif user.role == Role.EMPLOYEE:
            must.append(
                qmodels.FieldCondition(
                    key="allowed_user_ids", match=qmodels.MatchValue(value=str(user.id))
                )
            )

        exact_filters = {
            "department": filters.department_id,
            "document_id": filters.document_id,
            "page": filters.page,
            "channel": filters.channel,
            "thread": filters.thread,
        }
        for key, value in exact_filters.items():
            if value is not None:
                match_value = value if isinstance(value, int) else str(value)
                must.append(
                    qmodels.FieldCondition(key=key, match=qmodels.MatchValue(value=match_value))
                )
        return qmodels.Filter(must=must) if must else None

    @staticmethod
    def _result(point) -> SearchResult:
        payload = dict(point.payload or {})
        chunk = str(payload.pop("text", ""))
        document_id = payload.get("document_id")
        page = payload.get("page")
        return SearchResult(
            chunk=chunk,
            score=float(point.score),
            metadata=payload,
            page_number=int(page) if page is not None else None,
            document_id=document_id,
        )
