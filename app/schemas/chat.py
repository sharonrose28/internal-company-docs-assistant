from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    session_id: UUID | None = None


class Citation(BaseModel):
    source_id: str
    document_id: UUID
    document_name: str
    page_number: int | None = Field(default=None, ge=1)
    section_heading: str | None = None
    similarity_score: float
    quote: str


class ChatResponse(BaseModel):
    session_id: UUID
    answer: str | None
    status: str
    confidence: float = Field(ge=0, le=1)
    citations: list[Citation]


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    session_id: UUID
    question: str
    answer: str
    confidence: float
    citations: list[dict]
    created_at: datetime


class ChatSessionCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=200)


class ChatSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
