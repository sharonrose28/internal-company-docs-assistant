import hashlib
from uuid import UUID

from app.db.session import SessionFactory
from app.models.chat import AuditEvent


class AuditService:
    """Writes audit records in a transaction independent from the request transaction."""

    async def record(
        self,
        *,
        user_id: UUID,
        question: str,
        outcome: str,
        document_ids: list[str],
        chunk_ids: list[str],
        model: str | None,
        latency_ms: float,
        details: dict | None = None,
    ) -> None:
        async with SessionFactory.begin() as session:
            session.add(AuditEvent(
                user_id=user_id,
                action="rag.answer",
                outcome=outcome,
                question_hash=hashlib.sha256(question.encode("utf-8")).hexdigest(),
                document_ids=document_ids,
                chunk_ids=chunk_ids,
                model=model,
                latency_ms=latency_ms,
                details=details or {},
            ))
