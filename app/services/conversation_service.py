"""
Сервис для обработки диалогов с клиентами.
"""
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import structlog

from app.models.conversation import (
    ConversationResponse, 
    ConversationResult,
    EscalationResult,
    MessageResponse,
    SessionContext,
    Platform,
    ConversationStatus
)
from app.services.ai_service import AIService

logger = structlog.get_logger()


class ConversationService:
    """Сервис для управления диалогами с клиентами."""
    
    def __init__(self) -> None:
        self.ai_service = AIService()
        # TODO: Подключить к реальной БД
        self._sessions: Dict[str, SessionContext] = {}
        self._conversations: Dict[str, ConversationResponse] = {}
    
    async def process_conversation(
        self,
        user_id: str,
        session_id: str,
        message: str,
        intent: Optional[str] = None,
        entities: Optional[Dict[str, Any]] = None,
        platform: Platform = Platform.WEB
    ) -> ConversationResult:
        """
        Обработка сообщения в диалоге.
        
        Args:
            user_id: Идентификатор пользователя
            session_id: Идентификатор сессии
            message: Текст сообщения
            intent: Распознанное намерение
            entities: Извлеченные сущности
            platform: Платформа взаимодействия
            
        Returns:
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
            
            # Получаем или создаем контекст сессии
            context = await self._get_or_create_session_context(
                user_id, session_id, platform
            )
            
            # Добавляем сообщение пользователя в историю
            user_message = MessageResponse(
                id=str(uuid.uuid4()),
                content=message,
                message_type="user",
                user_id=user_id,
                session_id=session_id,
                platform=platform,
                created_at=datetime.now()
            )
            context.conversation_history.append(user_message)
            
            # Обновляем контекст сессии
            context.current_intent = intent
            context.entities = entities
            context.last_activity = datetime.now()
            
            # Генерируем ответ через AI сервис
            ai_response = await self.ai_service.generate_response(
                message=message,
                intent=intent,
                entities=entities,
                conversation_history=context.conversation_history,
                user_context=context.user_preferences
            )
            
            # Добавляем ответ AI в историю
            ai_message = MessageResponse(
                id=str(uuid.uuid4()),
                content=ai_response.response,
                message_type="assistant",
                user_id=user_id,
                session_id=session_id,
                platform=platform,
                created_at=datetime.now()
            )
            context.conversation_history.append(ai_message)
            
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
                next_questions=ai_response.next_questions
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
                escalation_reason="system_error"
            )
    
    async def get_user_sessions(self, user_id: str) -> List[ConversationResponse]:
        """Получить все сессии пользователя."""
        try:
            # TODO: Реализовать запрос к БД
            user_conversations = [
                conv for conv in self._conversations.values() 
                if conv.user_id == user_id
            ]
            return user_conversations
        except Exception as e:
            logger.error("Ошибка получения сессий пользователя", error=str(e), user_id=user_id)
            return []
    
    async def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Получить историю сообщений в сессии."""
        try:
            context = self._sessions.get(session_id)
            if not context:
                return []
            
            return [
                {
                    "id": msg.id,
                    "content": msg.content,
                    "type": msg.message_type,
                    "created_at": msg.created_at.isoformat()
                }
                for msg in context.conversation_history
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
        
        # Создаем новый контекст сессии
        context = SessionContext(
            user_id=user_id,
            session_id=session_id,
            platform=platform,
            conversation_history=[],
            last_activity=datetime.now()
        )
        
        # TODO: Загрузить предпочтения пользователя из БД
        
        self._sessions[session_id] = context
        return context
    
    async def _should_escalate_to_human(
        self,
        intent: Optional[str],
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
        if len(context.conversation_history) > 10:
            return True
        
        return False