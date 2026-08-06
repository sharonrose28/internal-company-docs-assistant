from dataclasses import dataclass
import hashlib
import json
from uuid import UUID

from app.core.exceptions import ForbiddenError
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.repositories.conversation import ConversationRepository
from app.repositories.document import DocumentRepository


@dataclass(frozen=True, slots=True)
class MemoryExchange:
    id: UUID
    question: str
    answer: str | None


@dataclass(frozen=True, slots=True)
class ConversationMemory:
    session: ChatSession
    exchanges: tuple[MemoryExchange, ...]

    @property
    def fingerprint(self) -> str:
        raw = f"{self.session.id}:" + ":".join(str(exchange.id) for exchange in self.exchanges)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


class ConversationMemoryService:
    MAX_EXCHANGES = 10

    def __init__(self, conversations: ConversationRepository, documents: DocumentRepository):
        self.conversations = conversations
        self.documents = documents

    async def load(
        self, user: User, session_id: UUID | None, first_question: str
    ) -> ConversationMemory:
        if session_id:
            session = await self.conversations.get_owned(session_id, user.id)
            if not session:
                raise ForbiddenError("You are not authorized to access this chat session")
        else:
            session = await self.conversations.create(user.id, self._title(first_question))
        messages = await self.conversations.last_exchanges(session.id, self.MAX_EXCHANGES)
        exchanges = await self._authorized_exchanges(user, messages)
        return ConversationMemory(session, tuple(exchanges))

    async def _authorized_exchanges(
        self, user: User, messages: list[ChatMessage]
    ) -> list[MemoryExchange]:
        message_documents: list[set[UUID]] = []
        for message in messages:
            document_ids = set()
            for citation in message.citations:
                try:
                    if citation.get("document_id"):
                        document_ids.add(UUID(str(citation["document_id"])))
                except (TypeError, ValueError):
                    continue
            message_documents.append(document_ids)
        all_document_ids = set().union(*message_documents) if message_documents else set()
        authorized = await self.documents.authorized_document_ids(user, all_document_ids)

        result = []
        for message, document_ids in zip(messages, message_documents, strict=True):
            answer = message.answer if document_ids and document_ids.issubset(authorized) else None
            result.append(MemoryExchange(message.id, message.question, answer))
        return result

    @staticmethod
    def retrieval_query(question: str, memory: ConversationMemory) -> str:
        previous = [exchange.question for exchange in memory.exchanges[-5:]]
        if not previous:
            return question
        context = "\n".join(f"- {item}" for item in previous)
        return f"Previous questions:\n{context}\nCurrent question:\n{question}"[:8000]

    @staticmethod
    def prompt_context(memory: ConversationMemory) -> str:
        exchanges = [
            {"question": exchange.question, "answer": exchange.answer}
            for exchange in memory.exchanges
        ]
        return json.dumps(exchanges, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _title(question: str) -> str:
        normalized = " ".join(question.split())
        return normalized[:80] or "New conversation"
