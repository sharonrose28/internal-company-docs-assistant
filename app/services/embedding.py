from dataclasses import dataclass
import logging
from time import monotonic
from uuid import UUID

from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient, models as qmodels

from app.core.config import Settings
from app.core.metrics import OPERATION_LATENCY

logger = logging.getLogger("app.embeddings")


@dataclass(frozen=True, slots=True)
class EmbeddingItem:
    chunk_id: UUID
    text: str
    payload: dict
    reusable_vector_id: str | None = None


class EmbeddingConfigurationError(RuntimeError):
    pass


class EmbeddingService:
    """Batched LangChain embeddings with checksum-based vector reuse and Qdrant upserts."""

    def __init__(self, settings: Settings, embeddings=None, sparse_embeddings=None, qdrant=None):
        if embeddings is None and (
            not settings.openai_api_key or not settings.openai_api_key.get_secret_value()
        ):
            raise EmbeddingConfigurationError("OPENAI_API_KEY is required by embedding workers")
        self.settings = settings
        self.embeddings = embeddings or OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.openai_api_key.get_secret_value(),
            chunk_size=settings.embedding_batch_size,
            max_retries=settings.embedding_max_retries,
            request_timeout=60,
        )
        if sparse_embeddings is None:
            # fastembed imports ONNX Runtime and allocates a meaningful amount of
            # memory. Keep it out of API and Celery module import paths so small
            # containers can start before an embedding task actually needs it.
            from fastembed import SparseTextEmbedding

            sparse_embeddings = SparseTextEmbedding(model_name="Qdrant/bm25")
        self.sparse_embeddings = sparse_embeddings
        self.qdrant = qdrant or QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
            timeout=30,
        )
        self._indexes_ensured = False

    def embed_and_store(self, items: list[EmbeddingItem]) -> dict[UUID, str]:
        if not items:
            return {}
        started = monotonic()
        reused = self._load_reusable_vectors(items)
        pending = [item for item in items if item.chunk_id not in reused]
        logger.info("embedding_batch_started", extra={
            "batch_size": len(items), "reused_count": len(reused),
            "api_input_count": len(pending), "model": self.settings.embedding_model,
        })

        generated: dict[UUID, list[float]] = {}
        if pending:
            embedding_started = monotonic()
            vectors = self.embeddings.embed_documents([item.text for item in pending])
            embedding_elapsed = monotonic() - embedding_started
            OPERATION_LATENCY.labels("document_embedding", "success").observe(embedding_elapsed)
            logger.info("embedding_generation_completed", extra={
                "batch_size": len(pending), "latency_ms": round(embedding_elapsed * 1000, 2),
                "model": self.settings.embedding_model,
            })
            if len(vectors) != len(pending):
                raise RuntimeError("Embedding provider returned an unexpected vector count")
            generated = {item.chunk_id: vector for item, vector in zip(pending, vectors, strict=True)}

        all_vectors = {**reused, **generated}
        vector_size = len(next(iter(all_vectors.values())))
        self._ensure_collection(vector_size)
        sparse_vectors = list(self.sparse_embeddings.embed([item.text for item in items]))
        if len(sparse_vectors) != len(items):
            raise RuntimeError("Sparse embedding provider returned an unexpected vector count")
        points = [
            qmodels.PointStruct(
                id=str(item.chunk_id),
                vector={
                    "dense": all_vectors[item.chunk_id],
                    "bm25": qmodels.SparseVector(
                        indices=sparse.indices.tolist(),
                        values=sparse.values.tolist(),
                    ),
                },
                payload=item.payload,
            )
            for item, sparse in zip(items, sparse_vectors, strict=True)
        ]
        qdrant_started = monotonic()
        self.qdrant.upsert(
            collection_name=self.settings.qdrant_collection,
            points=points,
            wait=True,
        )
        qdrant_elapsed = monotonic() - qdrant_started
        OPERATION_LATENCY.labels("qdrant_upsert", "success").observe(qdrant_elapsed)
        logger.info("qdrant_upsert_completed", extra={
            "point_count": len(points), "latency_ms": round(qdrant_elapsed * 1000, 2),
        })
        elapsed_ms = round((monotonic() - started) * 1000, 2)
        logger.info("embedding_batch_completed", extra={
            "batch_size": len(items), "reused_count": len(reused),
            "generated_count": len(generated), "latency_ms": elapsed_ms,
            "model": self.settings.embedding_model,
        })
        return {item.chunk_id: str(item.chunk_id) for item in items}

    def _load_reusable_vectors(self, items: list[EmbeddingItem]) -> dict[UUID, list[float]]:
        source_ids = {
            item.reusable_vector_id for item in items if item.reusable_vector_id is not None
        }
        if not source_ids or not self.qdrant.collection_exists(self.settings.qdrant_collection):
            return {}
        records = self.qdrant.retrieve(
            collection_name=self.settings.qdrant_collection,
            ids=list(source_ids),
            with_vectors=True,
            with_payload=False,
        )
        vectors_by_id = {
            str(record.id): record.vector["dense"]
            for record in records
            if isinstance(record.vector, dict) and record.vector.get("dense")
        }
        return {
            item.chunk_id: vectors_by_id[item.reusable_vector_id]
            for item in items
            if item.reusable_vector_id in vectors_by_id
        }

    def _ensure_collection(self, vector_size: int) -> None:
        collection = self.settings.qdrant_collection
        try:
            info = self.qdrant.get_collection(collection)
        except Exception as original_error:
            try:
                self.qdrant.create_collection(
                    collection_name=collection,
                    vectors_config={
                        "dense": qmodels.VectorParams(
                            size=vector_size,
                            distance=qmodels.Distance.COSINE,
                        )
                    },
                    sparse_vectors_config={
                        "bm25": qmodels.SparseVectorParams(
                            index=qmodels.SparseIndexParams(on_disk=False),
                            modifier=qmodels.Modifier.IDF,
                        )
                    },
                    hnsw_config=qmodels.HnswConfigDiff(m=16, ef_construct=128),
                )
            except Exception:
                if not self.qdrant.collection_exists(collection):
                    raise original_error
            self._ensure_payload_indexes()
            return
        configured = info.config.params.vectors
        configured_size = configured.get("dense").size if isinstance(configured, dict) and configured.get("dense") else None
        if configured_size != vector_size:
            raise EmbeddingConfigurationError(
                f"Qdrant collection has dimension {configured_size}; model returned {vector_size}"
            )
        self._ensure_payload_indexes()

    def _ensure_payload_indexes(self) -> None:
        if self._indexes_ensured:
            return
        fields = {
            "document_id": qmodels.PayloadSchemaType.KEYWORD,
            "department": qmodels.PayloadSchemaType.KEYWORD,
            "uploaded_by": qmodels.PayloadSchemaType.KEYWORD,
            "allowed_user_ids": qmodels.PayloadSchemaType.KEYWORD,
            "channel": qmodels.PayloadSchemaType.KEYWORD,
            "thread": qmodels.PayloadSchemaType.KEYWORD,
            "page": qmodels.PayloadSchemaType.INTEGER,
        }
        for field, schema in fields.items():
            self.qdrant.create_payload_index(
                collection_name=self.settings.qdrant_collection,
                field_name=field,
                field_schema=schema,
                wait=True,
            )
        self._indexes_ensured = True
