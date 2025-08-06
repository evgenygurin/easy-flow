"""SQLAlchemy модели для базы данных."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""


class User(Base):
    """Модель пользователя."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    user_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    preferences: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    conversations: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    """Модель диалога."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """Модель сообщения."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant, system
    message_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # NLP и AI данные
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entities: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="ru")

    # AI ответ данные
    ai_model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


class AIResponse(Base):
    """Модель AI ответа для аналитики."""

    __tablename__ = "ai_responses"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)

    # Входные данные
    original_message: Mapped[str] = mapped_column(Text, nullable=False)
    detected_intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    extracted_entities: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Ответ
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_type: Mapped[str] = mapped_column(String(50), nullable=False)  # template, knowledge_base, llm, fallback
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    suggested_actions: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    next_questions: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Метаданные
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    response_time_ms: Mapped[int] = mapped_column(nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    escalated_to_human: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeBaseItem(Base):
    """Модель элемента базы знаний."""

    __tablename__ = "knowledge_base"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[int] = mapped_column(default=1)  # 1-5, где 5 - наивысший

    # Метаданные
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version: Mapped[int] = mapped_column(default=1)

    # Статистика
    usage_count: Mapped[int] = mapped_column(default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ConversationMetrics(Base):
    """Модель метрик диалога."""

    __tablename__ = "conversation_metrics"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)

    # Метрики диалога
    total_messages: Mapped[int] = mapped_column(default=0)
    user_messages: Mapped[int] = mapped_column(default=0)
    ai_messages: Mapped[int] = mapped_column(default=0)
    duration_seconds: Mapped[int | None] = mapped_column(nullable=True)

    # AI метрики
    average_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    template_responses: Mapped[int] = mapped_column(default=0)
    knowledge_base_responses: Mapped[int] = mapped_column(default=0)
    llm_responses: Mapped[int] = mapped_column(default=0)
    fallback_responses: Mapped[int] = mapped_column(default=0)

    # Результат
    resolved_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    escalated_to_human: Mapped[bool] = mapped_column(Boolean, default=False)
    user_satisfaction: Mapped[int | None] = mapped_column(nullable=True)  # 1-5

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IntegrationLog(Base):
    """Модель логов интеграций с внешними системами."""

    __tablename__ = "integration_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)

    # Данные запроса
    request_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    response_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Метаданные
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, error, timeout
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
