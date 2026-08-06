from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.job import JobStatus
from app.schemas.document import DocumentRead


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    celery_task_id: str | None
    status: JobStatus
    stage: str
    progress: int = Field(ge=0, le=100)
    attempts: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    document: DocumentRead
    job: JobRead
