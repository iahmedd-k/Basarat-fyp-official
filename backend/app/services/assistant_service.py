from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.assistant import Conversation, Message


class AssistantService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_conversations(self, user_id: str) -> list[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_conversation(self, conversation_id: str, user_id: str) -> Conversation | None:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )
        return result.scalars().first()

    async def get_messages(self, conversation_id: str) -> list[Message]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())
