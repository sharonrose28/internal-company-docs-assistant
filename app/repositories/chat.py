from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession
from app.models.user import User


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, message: ChatMessage) -> ChatMessage:
        self.session.add(message)
        await self.session.flush()
        await self.session.execute(
            update(ChatSession).where(ChatSession.id == message.session_id).values(updated_at=func.now())
        )
        return message

    async def history(
        self, user: User, session_id, offset: int, limit: int
    ) -> list[ChatMessage]:
        result = await self.session.scalars(
            select(ChatMessage)
            .where(ChatMessage.user_id == user.id, ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(offset).limit(limit)
        )
        return list(result.all())
