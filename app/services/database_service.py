"""Сервис для работы с базой данных."""
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.conversation import ConversationStatus, MessageType, Platform
from app.models.database import (
    AIResponse,
    Base,
    Conversation,
    KnowledgeBaseItem,
    Message,
    User,
)


logger = structlog.get_logger()


class DatabaseService:
    """Сервис для работы с базой данных."""

    def __init__(self) -> None:
        if settings.DATABASE_URL:
            # Async engine для основных операций
            self.async_engine = create_async_engine(
                settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://'),
                echo=False,
                pool_size=20,
                max_overflow=30,
                pool_pre_ping=True,
                pool_recycle=3600
            )

            self.async_session_maker = async_sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            # Sync engine для миграций и административных задач
            self.sync_engine = create_engine(
                settings.DATABASE_URL,
                echo=False,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True
            )

            self.sync_session_maker = sessionmaker(self.sync_engine)

            self._available = True
            logger.info("База данных инициализирована", url=settings.DATABASE_URL.split('@')[-1])
        else:
            self.async_engine = None
            self.async_session_maker = None
            self.sync_engine = None
            self.sync_session_maker = None
            self._available = False
            logger.warning("DATABASE_URL не настроен, база данных недоступна")

    async def create_tables(self) -> bool:
        """Создать таблицы в базе данных."""
        if not self._available:
            return False

        try:
            async with self.async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Таблицы базы данных созданы")
            return True
        except Exception as e:
            logger.error("Ошибка создания таблиц", error=str(e))
            return False

    async def get_or_create_user(
        self,
        external_id: str,
        platform: Platform,
        metadata: dict[str, Any] | None = None
    ) -> User | None:
        """Получить или создать пользователя."""
        if not self._available:
            return None

        try:
            async with self.async_session_maker() as session:
                # Попытаться найти существующего пользователя
                stmt = select(User).where(
                    User.external_id == external_id,
                    User.platform == platform.value
                )
                result = await session.execute(stmt)
                user = result.scalars().first()

                if user:
                    # Обновить метаданные если они изменились
                    if metadata and metadata != user.metadata:
                        user.metadata = metadata
                        user.updated_at = datetime.utcnow()
                        await session.commit()
                    return user

                # Создать нового пользователя
                user = User(
                    external_id=external_id,
                    platform=platform.value,
                    metadata=metadata or {},
                    preferences={}
                )

                session.add(user)
                await session.commit()
                await session.refresh(user)

                logger.info("Создан новый пользователь", user_id=user.id, platform=platform.value)
                return user

        except Exception as e:
            logger.error("Ошибка получения/создания пользователя", error=str(e), external_id=external_id)
            return None

    async def create_conversation(
        self,
        user_id: str,
        session_id: str,
        platform: Platform,
        initial_context: dict[str, Any] | None = None
    ) -> Conversation | None:
        """Создать новый диалог."""
        if not self._available:
            return None

        try:
            async with self.async_session_maker() as session:
                conversation = Conversation(
                    user_id=user_id,
                    session_id=session_id,
                    platform=platform.value,
                    status=ConversationStatus.ACTIVE.value,
                    context=initial_context or {}
                )

                session.add(conversation)
                await session.commit()
                await session.refresh(conversation)

                logger.info("Создан новый диалог", conversation_id=conversation.id, user_id=user_id)
                return conversation

        except Exception as e:
            logger.error("Ошибка создания диалога", error=str(e), user_id=user_id)
            return None

    async def add_message(
        self,
        conversation_id: str,
        content: str,
        message_type: MessageType,
        metadata: dict[str, Any] | None = None,
        # NLP данные
        intent: str | None = None,
        entities: dict[str, Any] | None = None,
        confidence: float | None = None,
        sentiment: str | None = None,
        language: str = "ru",
        # AI данные
        ai_model_used: str | None = None,
        response_time_ms: int | None = None
    ) -> Message | None:
        """Добавить сообщение в диалог."""
        if not self._available:
            return None

        try:
            async with self.async_session_maker() as session:
                message = Message(
                    conversation_id=conversation_id,
                    content=content,
                    message_type=message_type.value,
                    metadata=metadata or {},
                    intent=intent,
                    entities=entities,
                    confidence=confidence,
                    sentiment=sentiment,
                    language=language,
                    ai_model_used=ai_model_used,
                    response_time_ms=response_time_ms
                )

                session.add(message)

                # Обновить время последней активности диалога
                stmt = select(Conversation).where(Conversation.id == conversation_id)
                result = await session.execute(stmt)
                conversation = result.scalars().first()

                if conversation:
                    conversation.updated_at = datetime.utcnow()

                await session.commit()
                await session.refresh(message)

                return message

        except Exception as e:
            logger.error("Ошибка добавления сообщения", error=str(e), conversation_id=conversation_id)
            return None

    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 50
    ) -> list[Message]:
        """Получить историю сообщений диалога."""
        if not self._available:
            return []

        try:
            async with self.async_session_maker() as session:
                stmt = (
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                messages = result.scalars().all()

                return list(reversed(messages))  # Возвращаем в хронологическом порядке

        except Exception as e:
            logger.error("Ошибка получения истории диалога", error=str(e), conversation_id=conversation_id)
            return []

    async def get_user_conversations(
        self,
        user_id: str,
        limit: int = 20
    ) -> list[Conversation]:
        """Получить диалоги пользователя."""
        if not self._available:
            return []

        try:
            async with self.async_session_maker() as session:
                stmt = (
                    select(Conversation)
                    .where(Conversation.user_id == user_id)
                    .order_by(Conversation.updated_at.desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                conversations = result.scalars().all()

                return list(conversations)

        except Exception as e:
            logger.error("Ошибка получения диалогов пользователя", error=str(e), user_id=user_id)
            return []

    async def log_ai_response(
        self,
        message_id: str,
        user_id: str,
        original_message: str,
        detected_intent: str | None,
        extracted_entities: dict[str, Any] | None,
        response_text: str,
        response_type: str,
        confidence: float,
        suggested_actions: list[str] | None,
        next_questions: list[str] | None,
        model_used: str | None,
        response_time_ms: int,
        cache_hit: bool = False,
        escalated_to_human: bool = False,
        escalation_reason: str | None = None
    ) -> AIResponse | None:
        """Записать лог AI ответа для аналитики."""
        if not self._available:
            return None

        try:
            async with self.async_session_maker() as session:
                ai_response = AIResponse(
                    message_id=message_id,
                    user_id=user_id,
                    original_message=original_message,
                    detected_intent=detected_intent,
                    extracted_entities=extracted_entities,
                    response_text=response_text,
                    response_type=response_type,
                    confidence=confidence,
                    suggested_actions=suggested_actions,
                    next_questions=next_questions,
                    model_used=model_used,
                    response_time_ms=response_time_ms,
                    cache_hit=cache_hit,
                    escalated_to_human=escalated_to_human,
                    escalation_reason=escalation_reason
                )

                session.add(ai_response)
                await session.commit()
                await session.refresh(ai_response)

                return ai_response

        except Exception as e:
            logger.error("Ошибка записи лога AI ответа", error=str(e))
            return None

    async def search_knowledge_base(
        self,
        keywords: list[str],
        category: str | None = None,
        limit: int = 5
    ) -> list[KnowledgeBaseItem]:
        """Поиск в базе знаний."""
        if not self._available:
            return []

        try:
            async with self.async_session_maker() as session:
                # Простой поиск по ключевым словам
                conditions = []
                for keyword in keywords:
                    conditions.append(func.array_to_string(KnowledgeBaseItem.keywords, ' ').ilike(f'%{keyword}%'))

                stmt = select(KnowledgeBaseItem).where(
                    KnowledgeBaseItem.is_active,
                    *conditions
                )

                if category:
                    stmt = stmt.where(KnowledgeBaseItem.category == category)

                stmt = stmt.order_by(
                    KnowledgeBaseItem.priority.desc(),
                    KnowledgeBaseItem.usage_count.desc()
                ).limit(limit)

                result = await session.execute(stmt)
                items = result.scalars().all()

                # Обновить счетчики использования
                for item in items:
                    item.usage_count += 1
                    item.last_used_at = datetime.utcnow()

                if items:
                    await session.commit()

                return list(items)

        except Exception as e:
            logger.error("Ошибка поиска в базе знаний", error=str(e))
            return []

    async def get_conversation_metrics_summary(
        self,
        days: int = 7
    ) -> dict[str, Any]:
        """Получить сводку метрик диалогов."""
        if not self._available:
            return {}

        try:
            async with self.async_session_maker() as session:
                since_date = datetime.utcnow() - timedelta(days=days)

                # Общие метрики
                total_conversations = await session.scalar(
                    select(func.count(Conversation.id))
                    .where(Conversation.created_at >= since_date)
                )

                total_messages = await session.scalar(
                    select(func.count(Message.id))
                    .where(Message.created_at >= since_date)
                )

                # AI метрики
                avg_confidence = await session.scalar(
                    select(func.avg(AIResponse.confidence))
                    .where(AIResponse.created_at >= since_date)
                )

                # Статистика по типам ответов
                response_types = await session.execute(
                    select(
                        AIResponse.response_type,
                        func.count().label('count')
                    )
                    .where(AIResponse.created_at >= since_date)
                    .group_by(AIResponse.response_type)
                )

                response_type_stats = {row.response_type: row.count for row in response_types}

                return {
                    "period_days": days,
                    "total_conversations": total_conversations or 0,
                    "total_messages": total_messages or 0,
                    "average_ai_confidence": float(avg_confidence or 0.0),
                    "response_type_distribution": response_type_stats
                }

        except Exception as e:
            logger.error("Ошибка получения метрик диалогов", error=str(e))
            return {}

    async def health_check(self) -> bool:
        """Проверка состояния базы данных."""
        if not self._available:
            return False

        try:
            async with self.async_session_maker() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error("База данных недоступна", error=str(e))
            return False

    async def close(self) -> None:
        """Закрытие соединений с базой данных."""
        if self.async_engine:
            await self.async_engine.dispose()
        if self.sync_engine:
            self.sync_engine.dispose()
        logger.info("Соединения с базой данных закрыты")


# Глобальный экземпляр сервиса базы данных
db_service = DatabaseService()
