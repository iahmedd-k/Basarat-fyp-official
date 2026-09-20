from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(datetime.utcnow().astimezone().tzinfo)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), default=lambda: datetime.now(datetime.utcnow().astimezone().tzinfo)
    )

    user = relationship("User", lazy="selectin")
    messages = relationship("AssistantMessage", back_populates="conversation", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_assistant_conversations_user_updated", "user_id", "updated_at"),
    )


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(datetime.utcnow().astimezone().tzinfo)
    )

    conversation = relationship("AssistantConversation", back_populates="messages", lazy="selectin")

    __table_args__ = (
        Index("ix_assistant_messages_conversation_created", "conversation_id", "created_at"),
    )