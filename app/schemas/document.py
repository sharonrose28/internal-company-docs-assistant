from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus, DocumentType


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    filename: str
    document_type: DocumentType
    status: DocumentStatus
    size_bytes: int
    department_id: UUID
    uploaded_by: UUID
    created_at: datetime


class DocumentList(BaseModel):
    items: list[DocumentRead]
    total: int

