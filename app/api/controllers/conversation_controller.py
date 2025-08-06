"""Контроллер для обработки диалогов с клиентами."""
import re
import uuid
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.api.controllers.base import BaseController
from app.models.conversation import Platform
from app.services.conversation_service import ConversationService
from app.services.nlp_service import NLPService


class ChatRequest(BaseModel):
    """Запрос на обработку сообщения в чате."""

    message: str = Field(..., min_length=1, max_length=4000, description="Текст сообщения от клиента")
    user_id: str = Field(..., min_length=1, max_length=100, description="Идентификатор пользователя")
    session_id: str | None = Field(None, min_length=1, max_length=100, description="Идентификатор сессии")
    platform: str = Field("web", description="Платформа (web, telegram, whatsapp, alice)")
    context: dict[str, Any] | None = Field(None, description="Дополнительный контекст")


class ChatResponse(BaseModel):
    """Ответ системы на сообщение."""

    message: str = Field(..., min_length=1, description="Ответ AI ассистента")
    session_id: str = Field(..., description="Идентификатор сессии")
    intent: str | None = Field(None, description="Распознанное намерение")
    entities: dict[str, Any] | None = Field(None, description="Извлеченные сущности")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Уверенность в ответе")
    requires_human: bool = Field(False, description="Требуется ли вмешательство человека")
    suggested_actions: list[str] | None = Field(None, description="Предлагаемые действия")
    current_state: str | None = Field(None, description="Текущее состояние диалога")
    state_transitions: int | None = Field(None, description="Количество переходов между состояниями")


class StateTransitionRequest(BaseModel):
    """Запрос на принудительный переход состояния."""

    state_name: str = Field(..., description="Название целевого состояния")
    reason: str | None = Field(None, description="Причина принудительного перехода")


class CleanupRequest(BaseModel):
    """Запрос на очистку неактивных сессий."""

    max_inactive_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Максимальное время неактивности в минутах (1-1440)"
    )


class ConversationController(BaseController):
    """Контроллер для обработки диалогов - только HTTP логика."""
    
    def __init__(
        self, 
        conversation_service: ConversationService,
        nlp_service: NLPService
    ) -> None:
        """Инициализация контроллера диалогов.
        
        Args:
        ----
            conversation_service: Сервис для работы с диалогами
            nlp_service: Сервис для обработки естественного языка
            
        """
        super().__init__()
        self.conversation_service = conversation_service
        self.nlp_service = nlp_service
    
    async def process_chat_message(self, request: ChatRequest) -> ChatResponse:
        """Обработка сообщения в чате - только валидация и делегирование.
        
        Args:
        ----
            request: Запрос на обработку сообщения
            
        Returns:
        -------
            ChatResponse: Результат обработки сообщения
            
        """
        # Валидация и обработка входных данных
        validated_request = self._validate_chat_request(request)
        
        # Делегирование бизнес-логики сервису
        return await self.handle_request(
            self._process_chat_message_business_logic,
            validated_request
        )
    
    async def get_user_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """Получить все сессии пользователя.
        
        Args:
        ----
            user_id: Идентификатор пользователя
            
        Returns:
        -------
            Список сессий пользователя
            
        """
        validated_user_id = self.validate_id(user_id, "user_id")
        
        return await self.handle_request(
            self.conversation_service.get_user_sessions,
            validated_user_id
        )
    
    async def get_session_history(self, session_id: str) -> list[dict[str, Any]]:
        """Получить историю сообщений в сессии.
        
        Args:
        ----
            session_id: Идентификатор сессии
            
        Returns:
        -------
            Список сообщений в сессии
            
        """
        validated_session_id = self.validate_id(session_id, "session_id")
        
        return await self.handle_request(
            self.conversation_service.get_session_history,
            validated_session_id
        )
    
    async def escalate_to_human(
        self, 
        session_id: str, 
        reason: str
    ) -> dict[str, str]:
        """Эскалация диалога к живому оператору.
        
        Args:
        ----
            session_id: Идентификатор сессии
            reason: Причина эскалации
            
        Returns:
        -------
            Результат эскалации
            
        """
        validated_session_id = self.validate_id(session_id, "session_id")
        
        if not reason or not reason.strip():
            raise HTTPException(
                status_code=400,
                detail="Причина эскалации не может быть пустой"
            )
        
        result = await self.handle_request(
            self.conversation_service.escalate_to_human,
            validated_session_id,
            reason.strip()
        )
        
        return {"status": "escalated", "ticket_id": result.ticket_id}
    
    async def get_flow_session_state(self, session_id: str) -> dict[str, Any]:
        """Получить состояние conversation flow сессии.
        
        Args:
        ----
            session_id: Идентификатор сессии
            
        Returns:
        -------
            Состояние сессии
            
        """
        validated_session_id = self.validate_id(session_id, "session_id")
        
        state = await self.handle_request(
            self.conversation_service.get_flow_session_state,
            validated_session_id
        )
        
        if not state:
            raise HTTPException(
                status_code=404,
                detail="Сессия не найдена"
            )
        
        return state
    
    async def reset_flow_session(self, session_id: str) -> dict[str, str]:
        """Сбросить conversation flow сессию.
        
        Args:
        ----
            session_id: Идентификатор сессии
            
        Returns:
        -------
            Результат сброса
            
        """
        validated_session_id = self.validate_id(session_id, "session_id")
        
        success = await self.handle_request(
            self.conversation_service.reset_flow_session,
            validated_session_id
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Сессия не найдена"
            )
        
        return {"status": "reset", "session_id": validated_session_id}
    
    async def force_flow_state_transition(
        self,
        session_id: str,
        request: StateTransitionRequest
    ) -> dict[str, str]:
        """Принудительный переход в состояние conversation flow.
        
        Args:
        ----
            session_id: Идентификатор сессии
            request: Запрос на переход состояния
            
        Returns:
        -------
            Результат перехода
            
        """
        validated_session_id = self.validate_id(session_id, "session_id")
        
        success = await self.handle_request(
            self.conversation_service.force_flow_state_transition,
            validated_session_id,
            request.state_name
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Не удалось выполнить переход состояния"
            )
        
        return {
            "status": "transitioned",
            "session_id": validated_session_id,
            "new_state": request.state_name
        }
    
    async def get_flow_metrics(self) -> dict[str, Any]:
        """Получить метрики conversation flow.
        
        Returns:
        -------
            Метрики conversation flow
            
        """
        return self.conversation_service.get_flow_metrics()
    
    async def cleanup_inactive_flow_sessions(
        self,
        request: CleanupRequest
    ) -> dict[str, int]:
        """Очистка неактивных conversation flow сессий.
        
        Args:
        ----
            request: Параметры очистки
            
        Returns:
        -------
            Результат очистки
            
        """
        cleaned_count = await self.handle_request(
            self.conversation_service.cleanup_inactive_flow_sessions,
            request.max_inactive_minutes
        )
        
        return {
            "cleaned_sessions": cleaned_count,
            "max_inactive_minutes": request.max_inactive_minutes
        }
    
    def _validate_chat_request(self, request: ChatRequest) -> ChatRequest:
        """Валидация запроса на чат.
        
        Args:
        ----
            request: Запрос для валидации
            
        Returns:
        -------
            Валидный запрос
            
        Raises:
        ------
            HTTPException: При ошибках валидации
            
        """
        # Валидация сообщения
        if not request.message or not request.message.strip():
            raise HTTPException(
                status_code=400,
                detail="Сообщение не может быть пустым"
            )
        
        # Очистка потенциально опасных символов
        cleaned_message = re.sub(r'[<>"]', '', request.message.strip())
        request.message = cleaned_message
        
        # Валидация user_id
        if not re.match(r'^[a-zA-Z0-9_-]+$', request.user_id):
            raise HTTPException(
                status_code=400,
                detail="user_id должен содержать только буквы, цифры, дефисы и подчеркивания"
            )
        
        # Валидация платформы
        allowed_platforms = ['web', 'telegram', 'whatsapp', 'alice', 'vk']
        if request.platform not in allowed_platforms:
            raise HTTPException(
                status_code=400,
                detail=f"Платформа должна быть одной из: {', '.join(allowed_platforms)}"
            )
        
        # Валидация session_id если предоставлен
        if request.session_id and not re.match(r'^[a-zA-Z0-9_-]+$', request.session_id):
            raise HTTPException(
                status_code=400,
                detail="Некорректный формат session_id"
            )
        
        return request
    
    async def _process_chat_message_business_logic(
        self,
        request: ChatRequest
    ) -> ChatResponse:
        """Бизнес-логика обработки сообщения чата - делегирование сервисам.
        
        Args:
        ----
            request: Валидный запрос
            
        Returns:
        -------
            ChatResponse: Результат обработки
            
        """
        # Генерируем session_id если не предоставлен (бизнес-логика теперь в контроллере)
        session_id = request.session_id or str(uuid.uuid4())
        
        # Обработка через NLP сервис
        nlp_result = await self.nlp_service.process_message(
            message=request.message,
            user_id=request.user_id,
            context=request.context
        )
        
        if not nlp_result:
            raise HTTPException(
                status_code=500,
                detail="Ошибка обработки NLP"
            )
        
        # Обработка через conversation сервис
        conversation_result = await self.conversation_service.process_conversation(
            user_id=request.user_id,
            session_id=session_id,
            message=request.message,
            intent=nlp_result.intent,
            entities=nlp_result.entities,
            platform=Platform(request.platform)
        )
        
        if not conversation_result:
            raise HTTPException(
                status_code=500,
                detail="Ошибка обработки диалога"
            )
        
        # Получение состояния conversation flow
        flow_state = await self.conversation_service.get_flow_session_state(session_id)
        current_state = flow_state.get("current_state") if flow_state else None
        state_transitions = flow_state.get("state_transitions") if flow_state else None
        
        # Формирование ответа
        return ChatResponse(
            message=conversation_result.response,
            session_id=session_id,
            intent=nlp_result.intent,
            entities=nlp_result.entities,
            confidence=nlp_result.confidence,
            requires_human=conversation_result.requires_human,
            suggested_actions=conversation_result.suggested_actions,
            current_state=current_state,
            state_transitions=state_transitions
        )