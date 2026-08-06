from uuid import UUID

from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class ChatMessage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_session_created", "session_id", "created_at"),)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), index=True)
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    citations: Mapped[list[dict]] = mapped_column(JSONB, default=list)


class ChatSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "chat_sessions"
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))


class AuditEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "audit_events"
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    outcome: Mapped[str] = mapped_column(String(50), index=True)
    question_hash: Mapped[str] = mapped_column(String(64), index=True)
    document_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    chunk_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    model: Mapped[str | None] = mapped_column(String(100))
    latency_ms: Mapped[float | None] = mapped_column(Float)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
