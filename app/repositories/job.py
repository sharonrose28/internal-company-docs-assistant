from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import IngestionJob, JobStatus


class JobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, document_id: UUID) -> IngestionJob:
        job = IngestionJob(document_id=document_id, status=JobStatus.QUEUED, stage="queued", progress=0)
        self.session.add(job)
        await self.session.flush()
        job.celery_task_id = str(job.id)
        return job

    async def get(self, job_id: UUID) -> IngestionJob | None:
        return await self.session.get(IngestionJob, job_id)

    async def failed_retryable(self, max_attempts: int, limit: int = 25) -> list[IngestionJob]:
        result = await self.session.scalars(
            select(IngestionJob)
            .where(IngestionJob.status == JobStatus.FAILED, IngestionJob.attempts < max_attempts)
            .order_by(IngestionJob.updated_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.all())

