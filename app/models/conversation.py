"""
Модели данных для диалогов и сообщений.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    """Тип сообщения."""
    USER = "user"
    ASSISTANT = "assistant" 
    SYSTEM = "system"


class Platform(str, Enum):
    """Платформы взаимодействия."""
    WEB = "web"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    VK = "vk"
    ALICE = "alice"
    VIBER = "viber"


class ConversationStatus(str, Enum):
    """Статус диалога."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    ABANDONED = "abandoned"


class MessageCreate(BaseModel):
    """Модель для создания нового сообщения."""
    content: str = Field(..., description="Текст сообщения")
    message_type: MessageType = Field(..., description="Тип сообщения")
    user_id: str = Field(..., description="ID пользователя")
    session_id: str = Field(..., description="ID сессии")
    platform: Platform = Field(Platform.WEB, description="Платформа")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Дополнительные данные")


class MessageResponse(BaseModel):
    """Модель ответа сообщения."""
    id: str
    content: str
    message_type: MessageType
    user_id: str
    session_id: str
    platform: Platform
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None


class ConversationCreate(BaseModel):
    """Модель для создания нового диалога."""
    user_id: str = Field(..., description="ID пользователя")
    platform: Platform = Field(Platform.WEB, description="Платформа")
    initial_message: str = Field(..., description="Первое сообщение")
    context: Optional[Dict[str, Any]] = Field(None, description="Контекст диалога")


class ConversationResponse(BaseModel):
    """Модель ответа диалога."""
    id: str
    user_id: str
    platform: Platform
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    messages_count: int
    context: Optional[Dict[str, Any]] = None
    last_message: Optional[str] = None


class ConversationUpdate(BaseModel):
    """Модель для обновления диалога."""
    status: Optional[ConversationStatus] = None
    context: Optional[Dict[str, Any]] = None


class NLPResult(BaseModel):
    """Результат обработки NLP."""
    intent: Optional[str] = Field(None, description="Распознанное намерение")
    entities: Optional[Dict[str, Any]] = Field(None, description="Извлеченные сущности")
    confidence: float = Field(0.0, description="Уверенность в результате")
    sentiment: Optional[str] = Field(None, description="Эмоциональная окраска")
    language: str = Field("ru", description="Язык сообщения")


class ConversationResult(BaseModel):
    """Результат обработки диалога."""
    response: str = Field(..., description="Ответ системы")
    requires_human: bool = Field(False, description="Требуется человек")
    suggested_actions: Optional[List[str]] = Field(None, description="Предложенные действия")
    next_questions: Optional[List[str]] = Field(None, description="Следующие вопросы")
    escalation_reason: Optional[str] = Field(None, description="Причина эскалации")


class EscalationResult(BaseModel):
    """Результат эскалации к человеку."""
    ticket_id: str = Field(..., description="ID тикета")
    agent_id: Optional[str] = Field(None, description="ID назначенного агента")
    estimated_wait_time: Optional[int] = Field(None, description="Ожидаемое время ожидания")
    priority: str = Field("normal", description="Приоритет тикета")


class SessionContext(BaseModel):
    """Контекст сессии пользователя."""
    user_id: str
    session_id: str
    platform: Platform
    conversation_history: List[MessageResponse] = []
    user_preferences: Optional[Dict[str, Any]] = None
    current_intent: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None
    last_activity: datetime