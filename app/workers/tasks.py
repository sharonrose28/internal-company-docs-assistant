import asyncio
from collections.abc import Awaitable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from celery import chord
from qdrant_client import QdrantClient, models as qmodels
from redis import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.ingestion import (
    MarkdownChunker,
    MarkdownParser,
    PDFExtractor,
    SemanticChunker,
    SlackConversationChunker,
    SlackExportParser,
)
from app.models.document import (
    ChunkStatus, Document, DocumentAssignment, DocumentChunk, DocumentStatus, DocumentType,
)
from app.models.job import IngestionJob, JobStatus
from app.services.embedding import EmbeddingItem, EmbeddingService
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


def _invalidate_cache_generation() -> int:
    client = Redis.from_url(get_settings().cache_redis_url, decode_responses=True)
    try:
        return int(client.incr("docs-cache:generation"))
    finally:
        client.close()


def _run(coro: Awaitable[Any]) -> Any:
    return asyncio.run(coro)


async def _with_session(operation):
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory.begin() as session:
            return await operation(session)
    finally:
        await engine.dispose()


async def _prepare_document(document_id: UUID) -> tuple[list[str], list[str]]:
    async def operation(session):
        document = await session.get(Document, document_id, with_for_update=True)
        if not document:
            raise ValueError(f"Document {document_id} does not exist")
        document.status = DocumentStatus.PROCESSING
        document.error_message = None
        stale_vector_ids = list((await session.scalars(
            select(DocumentChunk.vector_id).where(
                DocumentChunk.document_id == document.id,
                DocumentChunk.vector_id.is_not(None),
            )
        )).all())
        await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

        path = (get_settings().upload_dir / Path(document.storage_key).name).resolve()
        if path.parent != get_settings().upload_dir.resolve() or not path.is_file():
            raise ValueError("Document storage path is invalid or missing")

        if document.document_type == DocumentType.PDF:
            pages = PDFExtractor().extract(path)
            extracted = SemanticChunker(
                get_settings().chunk_size_tokens, get_settings().chunk_overlap_tokens
            ).split(pages)
            chunks = [
                {
                    "text": chunk.text,
                    "token_count": chunk.token_count,
                    "page": chunk.page,
                    "section": chunk.section,
                    "heading_path": None,
                    "line_start": None,
                    "line_end": None,
                    "channel": None,
                    "thread": None,
                    "participants": None,
                }
                for chunk in extracted
            ]
        elif document.document_type == DocumentType.MARKDOWN:
            sections = MarkdownParser().parse(path)
            extracted = MarkdownChunker(
                get_settings().chunk_size_tokens, get_settings().chunk_overlap_tokens
            ).split(sections)
            chunks = [
                {
                    "text": chunk.text,
                    "token_count": chunk.token_count,
                    "page": None,
                    "section": chunk.heading_path[-1] if chunk.heading_path else None,
                    "heading_path": list(chunk.heading_path),
                    "line_start": chunk.line_start,
                    "line_end": chunk.line_end,
                    "channel": None,
                    "thread": None,
                    "participants": None,
                }
                for chunk in extracted
            ]
        elif document.document_type == DocumentType.SLACK_JSON:
            conversations = SlackExportParser().parse(path)
            extracted = SlackConversationChunker(
                get_settings().chunk_size_tokens, get_settings().chunk_overlap_tokens
            ).split(conversations)
            chunks = [
                {
                    "text": chunk.text,
                    "token_count": chunk.token_count,
                    "page": None,
                    "section": None,
                    "heading_path": None,
                    "line_start": None,
                    "line_end": None,
                    "channel": chunk.channel,
                    "thread": chunk.thread,
                    "participants": list(chunk.participants),
                }
                for chunk in extracted
            ]
        else:
            raise ValueError(f"No ingestion pipeline exists for {document.document_type.value}")
        if not chunks:
            raise ValueError("No ingestible text was found in the document")

        rows = [
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                text=chunk["text"],
                token_count=chunk["token_count"],
                filename=document.filename,
                page=chunk["page"],
                department_id=document.department_id,
                section=chunk["section"],
                heading_path=chunk["heading_path"],
                line_start=chunk["line_start"],
                line_end=chunk["line_end"],
                channel=chunk["channel"],
                thread=chunk["thread"],
                participants=chunk["participants"],
                status=ChunkStatus.PENDING,
            )
            for index, chunk in enumerate(chunks)
        ]
        session.add_all(rows)
        await session.flush()
        return [str(row.id) for row in rows], stale_vector_ids

    return await _with_session(operation)


async def _update_job(
    job_id: UUID,
    *,
    status: JobStatus,
    stage: str,
    progress: int,
    error: str | None = None,
    task_id: str | None = None,
    increment_attempt: bool = False,
) -> None:
    async def operation(session):
        job = await session.get(IngestionJob, job_id, with_for_update=True)
        if not job:
            raise ValueError(f"Ingestion job {job_id} does not exist")
        job.status = status
        job.stage = stage
        job.progress = max(0, min(progress, 100))
        job.error_message = error[:2000] if error else None
        if task_id:
            job.celery_task_id = task_id
        if increment_attempt:
            job.attempts += 1
            job.started_at = datetime.now(UTC)
        if status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
            job.completed_at = datetime.now(UTC)
    await _with_session(operation)


async def _refresh_embedding_progress(job_id: UUID) -> None:
    async def operation(session):
        job = await session.get(IngestionJob, job_id, with_for_update=True)
        if not job:
            return
        total = await session.scalar(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.document_id == job.document_id
            )
        ) or 0
        completed = await session.scalar(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.document_id == job.document_id,
                DocumentChunk.status.in_([ChunkStatus.EMBEDDED, ChunkStatus.FAILED]),
            )
        ) or 0
        job.stage = "embedding_and_qdrant"
        job.progress = 35 + int(55 * completed / total) if total else 35
    await _with_session(operation)


async def _mark_document_failed(document_id: UUID, error: str) -> None:
    async def operation(session):
        document = await session.get(Document, document_id)
        if document:
            document.status = DocumentStatus.FAILED
            document.error_message = error[:2000]
    await _with_session(operation)


async def _load_embedding_items(chunk_ids: list[UUID]) -> tuple[list[EmbeddingItem], str]:
    async def operation(session):
        rows = (
            await session.execute(
                select(DocumentChunk, Document)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(DocumentChunk.id.in_(chunk_ids))
                .order_by(DocumentChunk.chunk_index)
            )
        ).all()
        if len(rows) != len(chunk_ids):
            raise ValueError("One or more embedding chunks no longer exist")
        checksums = {document.content_sha256 for _, document in rows}
        document_ids = {chunk.document_id for chunk, _ in rows}
        if len(checksums) != 1 or len(document_ids) != 1:
            raise ValueError("An embedding batch must belong to one document checksum")
        checksum = next(iter(checksums))
        allowed_user_ids = [
            str(user_id) for user_id in (
                await session.scalars(
                    select(DocumentAssignment.user_id).where(
                        DocumentAssignment.document_id == next(iter(document_ids))
                    )
                )
            ).all()
        ]

        prior_chunk = aliased(DocumentChunk)
        prior_document = aliased(Document)
        prior_rows = (
            await session.execute(
                select(prior_chunk)
                .join(prior_document, prior_document.id == prior_chunk.document_id)
                .where(
                    prior_document.content_sha256 == checksum,
                    prior_chunk.document_id != next(iter(document_ids)),
                    prior_chunk.chunk_index.in_([chunk.chunk_index for chunk, _ in rows]),
                    prior_chunk.status == ChunkStatus.EMBEDDED,
                    prior_chunk.embedding_model == get_settings().embedding_model,
                    prior_chunk.vector_id.is_not(None),
                )
                .order_by(prior_chunk.updated_at.desc())
            )
        ).scalars().all()
        reusable = {}
        for prior in prior_rows:
            reusable.setdefault((prior.chunk_index, prior.text), prior.vector_id)

        items = [
            EmbeddingItem(
                chunk_id=chunk.id,
                text=chunk.text,
                reusable_vector_id=reusable.get((chunk.chunk_index, chunk.text)),
                payload={
                    "document_id": str(chunk.document_id),
                    "chunk_id": str(chunk.id),
                    "filename": chunk.filename,
                    "page": chunk.page,
                    "department": str(chunk.department_id),
                    "section": chunk.section,
                    "heading_path": chunk.heading_path,
                    "line_start": chunk.line_start,
                    "line_end": chunk.line_end,
                    "channel": chunk.channel,
                    "thread": chunk.thread,
                    "participants": chunk.participants,
                    "text": chunk.text,
                    "document_checksum": checksum,
                    "uploaded_by": str(document.uploaded_by),
                    "allowed_user_ids": allowed_user_ids,
                },
            )
            for chunk, document in rows
        ]
        return items, checksum
    return await _with_session(operation)


async def _set_batch_success(vector_ids: dict[UUID, str], checksum: str) -> None:
    async def operation(session):
        chunks = (
            await session.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(vector_ids)))
        ).all()
        if len(chunks) != len(vector_ids):
            raise ValueError("Cannot persist all Qdrant vector identifiers")
        for chunk in chunks:
            chunk.vector_id = vector_ids[chunk.id]
            chunk.embedding_model = get_settings().embedding_model
            chunk.embedding_checksum = checksum
            chunk.embedded_at = datetime.now(UTC)
            chunk.status = ChunkStatus.EMBEDDED
            chunk.error_message = None
    await _with_session(operation)


async def _set_batch_failed(chunk_ids: list[UUID], error: str) -> None:
    async def operation(session):
        chunks = (
            await session.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids)))
        ).all()
        for chunk in chunks:
            chunk.status = ChunkStatus.FAILED
            chunk.error_message = error[:2000]
    await _with_session(operation)


@celery_app.task(bind=True, name="documents.extract", max_retries=0)
def process_document(self, document_id: str, job_id: str) -> dict:
    parsed_id = UUID(document_id)
    parsed_job_id = UUID(job_id)
    _run(_update_job(
        parsed_job_id,
        status=JobStatus.RUNNING,
        stage="extracting",
        progress=5,
        task_id=self.request.id,
        increment_attempt=True,
    ))
    self.update_state(state="PROGRESS", meta={"stage": "extracting", "progress": 5})
    try:
        chunk_ids, stale_vector_ids = _run(_prepare_document(parsed_id))
    except Exception as exc:
        _run(_mark_document_failed(parsed_id, str(exc)))
        _run(_update_job(
            parsed_job_id,
            status=JobStatus.FAILED,
            stage="extraction_failed",
            progress=100,
            error=str(exc),
        ))
        logger.exception("document_parsing_failed", document_id=document_id)
        return {"document_id": document_id, "status": "failed", "error": str(exc)}

    if stale_vector_ids:
        delete_document_vectors(stale_vector_ids)
    _run(_update_job(
        parsed_job_id,
        status=JobStatus.RUNNING,
        stage="chunked",
        progress=30,
    ))
    self.update_state(state="PROGRESS", meta={"stage": "chunked", "progress": 30})

    batch_size = get_settings().embedding_batch_size
    batches = [chunk_ids[start:start + batch_size] for start in range(0, len(chunk_ids), batch_size)]
    workflow = chord(generate_embedding_batch.s(batch, job_id) for batch in batches)
    workflow(finalize_document.s(document_id, job_id))
    return {
        "document_id": document_id,
        "status": "embedding",
        "chunks": len(chunk_ids),
        "batches": len(batches),
    }


@celery_app.task(
    bind=True,
    name="documents.generate_embedding_batch",
    max_retries=get_settings().embedding_max_retries,
)
def generate_embedding_batch(self, chunk_ids: list[str], job_id: str) -> dict:
    parsed_ids = [UUID(chunk_id) for chunk_id in chunk_ids]
    try:
        items, checksum = _run(_load_embedding_items(parsed_ids))
        vector_ids = EmbeddingService(get_settings()).embed_and_store(items)
        _run(_set_batch_success(vector_ids, checksum))
        _run(_refresh_embedding_progress(UUID(job_id)))
        self.update_state(
            state="PROGRESS",
            meta={"stage": "embedding_and_qdrant", "chunk_count": len(chunk_ids)},
        )
        return {"chunk_ids": chunk_ids, "ok": True, "count": len(chunk_ids)}
    except Exception as exc:
        if self.request.retries < self.max_retries:
            countdown = min(2 ** (self.request.retries + 1), 60)
            logger.warning(
                "embedding_batch_retry",
                chunk_count=len(chunk_ids),
                attempt=self.request.retries + 1,
                countdown=countdown,
                error_type=type(exc).__name__,
            )
            _run(_update_job(
                UUID(job_id),
                status=JobStatus.RETRYING,
                stage="embedding_retry",
                progress=35,
                error=str(exc),
            ))
            raise self.retry(exc=exc, countdown=countdown)
        _run(_set_batch_failed(parsed_ids, str(exc)))
        _run(_refresh_embedding_progress(UUID(job_id)))
        logger.exception(
            "embedding_batch_failed",
            chunk_count=len(chunk_ids),
            attempts=self.request.retries + 1,
            error_type=type(exc).__name__,
        )
        return {"chunk_ids": chunk_ids, "ok": False, "error": str(exc)}


@celery_app.task(
    name="documents.finalize",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=5,
)
def finalize_document(results: list[dict], document_id: str, job_id: str) -> dict:
    succeeded = all(result.get("ok") for result in results)

    async def operation(session):
        document = await session.get(Document, UUID(document_id), with_for_update=True)
        if document:
            document.status = DocumentStatus.READY if succeeded else DocumentStatus.FAILED
            document.error_message = None if succeeded else "One or more chunks failed to embed"
    _run(_with_session(operation))
    _run(_update_job(
        UUID(job_id),
        status=JobStatus.SUCCEEDED if succeeded else JobStatus.FAILED,
        stage="completed" if succeeded else "embedding_failed",
        progress=100,
        error=None if succeeded else "One or more embedding batches failed",
    ))
    _invalidate_cache_generation()
    return {"document_id": document_id, "status": "ready" if succeeded else "failed"}


@celery_app.task(name="documents.delete_file", autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def delete_document_file(storage_key: str) -> None:
    upload_root = get_settings().upload_dir.resolve()
    target = (upload_root / Path(storage_key).name).resolve()
    if target.parent != upload_root:
        raise ValueError("Invalid storage key")
    target.unlink(missing_ok=True)


@celery_app.task(name="documents.delete_vectors", autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def delete_document_vectors(vector_ids: list[str]) -> None:
    if not vector_ids:
        return
    settings = get_settings()
    QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
        timeout=30,
    ).delete(
        collection_name=get_settings().qdrant_collection,
        points_selector=qmodels.PointIdsList(points=vector_ids),
        wait=True,
    )


@celery_app.task(name="documents.sync_permissions", autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def sync_document_permissions(document_id: str) -> None:
    parsed_id = UUID(document_id)

    async def operation(session):
        user_ids = list((await session.scalars(
            select(DocumentAssignment.user_id).where(DocumentAssignment.document_id == parsed_id)
        )).all())
        vector_ids = list((await session.scalars(
            select(DocumentChunk.vector_id).where(
                DocumentChunk.document_id == parsed_id,
                DocumentChunk.vector_id.is_not(None),
            )
        )).all())
        return [str(user_id) for user_id in user_ids], vector_ids

    allowed_user_ids, vector_ids = _run(_with_session(operation))
    if vector_ids:
        settings = get_settings()
        QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
            timeout=30,
        ).set_payload(
            collection_name=get_settings().qdrant_collection,
            payload={"allowed_user_ids": allowed_user_ids},
            points=vector_ids,
            wait=True,
        )
    _invalidate_cache_generation()


@celery_app.task(
    name="documents.invalidate_cache",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=5,
)
def invalidate_document_cache() -> int:
    return _invalidate_cache_generation()
