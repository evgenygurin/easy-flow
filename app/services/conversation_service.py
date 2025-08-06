"""Сервис для обработки диалогов с клиентами."""
import uuid
from datetime import datetime
from typing import Any

import structlog

from app.models.conversation import (
    ConversationResponse,
    ConversationResult,
    EscalationResult,
    MessageResponse,
    MessageType,
    Platform,
    SessionContext,
)
from app.repositories.interfaces.conversation_repository import ConversationRepository
from app.repositories.interfaces.message_repository import MessageRepository
from app.repositories.interfaces.user_repository import UserRepository
from app.services.ai_service import AIService
from app.services.flow.flow_service import ConversationFlowService


logger = structlog.get_logger()


class ConversationService:
    """Сервис для управления диалогами с клиентами."""

    def __init__(
        self,
        user_repository: UserRepository,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository
    ) -> None:
        self.user_repository = user_repository
        self.conversation_repository = conversation_repository
        self.message_repository = message_repository
        self.ai_service = AIService()
        self.flow_service = ConversationFlowService()
        # In-memory sessions for flow state - TODO: Consider persistent storage
        self._sessions: dict[str, SessionContext] = {}

    async def process_conversation(
        self,
        user_id: str,
        session_id: str,
        message: str,
        intent: str | None = None,
        entities: dict[str, Any] | None = None,
        platform: Platform = Platform.WEB
    ) -> ConversationResult:
        """Обработка сообщения в диалоге.

        Args:
        ----
            user_id: Идентификатор пользователя
            session_id: Идентификатор сессии
            message: Текст сообщения
            intent: Распознанное намерение
            entities: Извлеченные сущности
            platform: Платформа взаимодействия

        Returns:
        -------
            ConversationResult: Результат обработки диалога

        """
        try:
            logger.info(
                "Обработка сообщения в диалоге",
                user_id=user_id,
                session_id=session_id,
                intent=intent,
                platform=platform.value
            )

            # Получаем или создаем пользователя
            user = await self.user_repository.get_or_create_user(
                external_id=user_id,
                platform=platform
            )
            if not user:
                raise ValueError(f"Failed to get/create user {user_id}")

            # Получаем или создаем диалог
            conversation = await self.conversation_repository.get_by_session_id(session_id)
            if not conversation:
                conversation = await self.conversation_repository.create_conversation(
                    user_id=user.id,
                    session_id=session_id,
                    platform=platform
                )
                if not conversation:
                    raise ValueError(f"Failed to create conversation for session {session_id}")

            # Добавляем сообщение пользователя в БД
            user_message = await self.message_repository.add_message(
                conversation_id=conversation.id,
                content=message,
                message_type=MessageType.USER,
                intent=intent,
                entities=entities
            )
            if not user_message:
                raise ValueError("Failed to add user message")

            # Получаем или создаем контекст сессии для flow service
            context = await self._get_or_create_session_context(
                user.id, session_id, platform
            )

            # Обновляем контекст сессии
            context.current_intent = intent
            context.entities = entities
            context.last_activity = datetime.now()

            # Обрабатываем через conversation flow (новая система состояний)
            try:
                flow_result = await self.flow_service.process_conversation_flow(
                    user_id=user_id,
                    session_id=session_id,
                    message=message,
                    platform=platform,
                    intent=intent,
                    entities=entities
                )

                # Добавляем ответ AI в БД
                ai_message = await self.message_repository.add_message(
                    conversation_id=conversation.id,
                    content=flow_result.response,
                    message_type=MessageType.ASSISTANT
                )

                # Сохраняем обновленный контекст
                self._sessions[session_id] = context

                return flow_result

            except Exception as flow_error:
                logger.warning(
                    "Ошибка в conversation flow, переходим на fallback",
                    error=str(flow_error)
                )

                # Fallback на старую логику AI сервиса
                ai_response = await self.ai_service.generate_response(
                    message=message,
                    intent=intent,
                    entities=entities,
                    conversation_history=context.conversation_history,
                    user_context=context.user_preferences
                )

                # Добавляем ответ AI в БД
                ai_message = await self.message_repository.add_message(
                    conversation_id=conversation.id,
                    content=ai_response.response,
                    message_type=MessageType.ASSISTANT
                )

                # Сохраняем обновленный контекст
                self._sessions[session_id] = context

                # Проверяем необходимость эскалации
                requires_human = await self._should_escalate_to_human(
                    intent, ai_response.confidence, context
                )

                return ConversationResult(
                    response=ai_response.response,
                    requires_human=requires_human,
                    suggested_actions=ai_response.suggested_actions,
                    next_questions=ai_response.next_questions,
                    escalation_reason=None
                )

        except Exception as e:
            logger.error(
                "Ошибка обработки диалога",
                error=str(e),
                user_id=user_id,
                session_id=session_id
            )
            # Возвращаем fallback ответ
            return ConversationResult(
                response="Извините, произошла ошибка. Попробуйте переформулировать вопрос.",
                requires_human=True,
                suggested_actions=None,
                next_questions=None,
                escalation_reason="system_error"
            )

    async def get_user_sessions(self, user_id: str) -> list[ConversationResponse]:
        """Получить все сессии пользователя."""
        try:
            # Get user first
            user = await self.user_repository.get_by_external_id(user_id, Platform.WEB)
            if not user:
                return []
            
            # Get user conversations from repository
            conversations = await self.conversation_repository.get_user_conversations(user.id)
            
            # Convert to ConversationResponse format
            conversation_responses = []
            for conv in conversations:
                conversation_responses.append(ConversationResponse(
                    id=conv.id,
                    user_id=conv.user_id,
                    session_id=conv.session_id,
                    platform=Platform(conv.platform),
                    status=conv.status,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                    context=conv.context
                ))
            
            return conversation_responses
        except Exception as e:
            logger.error("Ошибка получения сессий пользователя", error=str(e), user_id=user_id)
            return []

    async def get_session_history(self, session_id: str) -> list[dict[str, Any]]:
        """Получить историю сообщений в сессии."""
        try:
            # Get conversation by session ID
            conversation = await self.conversation_repository.get_by_session_id(session_id)
            if not conversation:
                return []
            
            # Get message history from repository
            messages = await self.message_repository.get_conversation_history(conversation.id)
            
            return [
                {
                    "id": msg.id,
                    "content": msg.content,
                    "type": msg.message_type,
                    "created_at": msg.created_at.isoformat()
                }
                for msg in messages
            ]
        except Exception as e:
            logger.error("Ошибка получения истории сессии", error=str(e), session_id=session_id)
            return []

    async def escalate_to_human(self, session_id: str, reason: str) -> EscalationResult:
        """Эскалация диалога к живому оператору."""
        try:
            context = self._sessions.get(session_id)
            if not context:
                raise ValueError(f"Сессия {session_id} не найдена")

            # Создаем тикет для оператора
            ticket_id = str(uuid.uuid4())

            # TODO: Интеграция с системой тикетов (Zendesk, Freshdesk и т.д.)

            logger.info(
                "Диалог эскалирован к оператору",
                session_id=session_id,
                ticket_id=ticket_id,
                reason=reason
            )

            return EscalationResult(
                ticket_id=ticket_id,
                agent_id=None,
                estimated_wait_time=300,  # 5 минут
                priority="normal"
            )

        except Exception as e:
            logger.error("Ошибка эскалации к оператору", error=str(e), session_id=session_id)
            raise

    async def _get_or_create_session_context(
        self,
        user_id: str,
        session_id: str,
        platform: Platform
    ) -> SessionContext:
        """Получить или создать контекст сессии."""
        if session_id in self._sessions:
            return self._sessions[session_id]

        # Создаем новый контекст сессии для flow service
        context = SessionContext(
            user_id=user_id,
            session_id=session_id,
            platform=platform,
            conversation_history=[],
            last_activity=datetime.now()
        )

        # Загружаем предпочтения пользователя из БД
        user = await self.user_repository.get_by_external_id(user_id, platform)
        if user and user.preferences:
            context.user_preferences = user.preferences

        self._sessions[session_id] = context
        return context

    async def _should_escalate_to_human(
        self,
        intent: str | None,
        confidence: float,
        context: SessionContext
    ) -> bool:
        """Определить необходимость эскалации к человеку."""
        # Низкая уверенность AI
        if confidence < 0.5:
            return True

        # Определенные намерения требуют человека
        human_required_intents = [
            "complaint",
            "refund_request",
            "technical_issue",
            "billing_dispute"
        ]

        if intent in human_required_intents:
            return True

        # Много сообщений без разрешения проблемы
        return len(context.conversation_history) > 10

    # Методы для работы с conversation flow

    async def get_flow_session_state(self, session_id: str) -> dict[str, Any] | None:
        """Получить состояние conversation flow сессии."""
        return await self.flow_service.get_session_state(session_id)

    async def reset_flow_session(self, session_id: str) -> bool:
        """Сбросить conversation flow сессию."""
        return await self.flow_service.reset_session(session_id)

    async def force_flow_state_transition(self, session_id: str, state_name: str) -> bool:
        """Принудительный переход в состояние conversation flow."""
        return await self.flow_service.force_state_transition(session_id, state_name)

    def get_flow_metrics(self) -> dict[str, Any]:
        """Получить метрики conversation flow."""
        return self.flow_service.get_flow_metrics()

    async def cleanup_inactive_flow_sessions(self, max_inactive_minutes: int = 30) -> int:
        """Очистка неактивных conversation flow сессий."""
        return await self.flow_service.cleanup_inactive_sessions(max_inactive_minutes)
