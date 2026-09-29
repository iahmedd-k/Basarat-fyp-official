from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, ConfigDict, Field


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = Field(None, max_length=36)


class AssistantChatResponse(BaseModel):
    message: str
    conversation_id: str
    intent: Optional[str] = None
    safety_filtered: bool = False


class AssistantQuickPrompt(BaseModel):
    id: str
    label: str
    message: str


class AssistantQuickPromptsResponse(BaseModel):
    prompts: List[AssistantQuickPrompt]


class AssistantMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class AssistantConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AssistantConversationListResponse(BaseModel):
    conversations: List[AssistantConversationResponse]


class AssistantConversationCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)


class AssistantConversationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)


class AssistantConversationMessagesResponse(BaseModel):
    messages: List[AssistantMessageResponse]
    conversation: AssistantConversationResponse