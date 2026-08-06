from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: UUID, title: str) -> ChatSession:
        conversation = ChatSession(user_id=user_id, title=title[:200])
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get_owned(self, session_id: UUID, user_id: UUID) -> ChatSession | None:
        return await self.session.scalar(select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        ))

    async def list_owned(self, user_id: UUID, offset: int, limit: int) -> list[ChatSession]:
        result = await self.session.scalars(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .offset(offset).limit(limit)
        )
        return list(result.all())

    async def last_exchanges(self, session_id: UUID, limit: int = 10) -> list[ChatMessage]:
        result = list((await self.session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(min(limit, 10))
        )).all())
        return list(reversed(result))

    async def delete_owned(self, session_id: UUID, user_id: UUID) -> bool:
        result = await self.session.execute(
            delete(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        return bool(result.rowcount)
