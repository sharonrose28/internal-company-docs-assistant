import enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SearchMode(str, enum.Enum):
    HYBRID = "hybrid"
    SEMANTIC = "semantic"


class SearchFilters(BaseModel):
    department_id: UUID | None = None
    document_id: UUID | None = None
    page: int | None = Field(default=None, ge=1)
    channel: str | None = Field(default=None, max_length=255)
    thread: str | None = Field(default=None, max_length=64)


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    mode: SearchMode = SearchMode.HYBRID
    filters: SearchFilters = Field(default_factory=SearchFilters)


class SearchResult(BaseModel):
    chunk: str
    score: float
    metadata: dict[str, Any]
    page_number: int | None
    document_id: UUID


class SearchResponse(BaseModel):
    items: list[SearchResult]
    top_k: int = 5

