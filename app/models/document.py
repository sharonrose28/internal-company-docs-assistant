import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class DocumentType(str, enum.Enum):
    PDF = "pdf"
    MARKDOWN = "markdown"
    SLACK_JSON = "slack_json"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ChunkStatus(str, enum.Enum):
    PENDING = "pending"
    EMBEDDED = "embedded"
    FAILED = "failed"


class Document(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    title: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    document_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType, name="document_type"))
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"), default=DocumentStatus.UPLOADED, index=True
    )
    storage_key: Mapped[str] = mapped_column(Text, unique=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    department_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("departments.id"), index=True)
    uploaded_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), index=True)


class DocumentChunk(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(255))
    page: Mapped[int | None] = mapped_column(Integer)
    department_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True)
    section: Mapped[str | None] = mapped_column(String(500))
    heading_path: Mapped[list[str] | None] = mapped_column(JSONB)
    line_start: Mapped[int | None] = mapped_column(Integer)
    line_end: Mapped[int | None] = mapped_column(Integer)
    channel: Mapped[str | None] = mapped_column(String(255), index=True)
    thread: Mapped[str | None] = mapped_column(String(64), index=True)
    participants: Mapped[list[str] | None] = mapped_column(JSONB)
    vector_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    embedding_checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ChunkStatus] = mapped_column(
        Enum(ChunkStatus, name="chunk_status"), default=ChunkStatus.PENDING, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text)


class DocumentAssignment(Base):
    __tablename__ = "document_assignments"
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    assigned_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
