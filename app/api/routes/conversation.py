"""
API endpoints для обработки диалогов с клиентами.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import re

from app.services.conversation_service import ConversationService
from app.services.nlp_service import NLPService
from app.models.conversation import ConversationCreate, ConversationResponse, MessageCreate

router = APIRouter()


class ChatRequest(BaseModel):
    """Запрос на обработку сообщения в чате."""
    message: str = Field(..., min_length=1, max_length=4000, description="Текст сообщения от клиента")
    user_id: str = Field(..., min_length=1, max_length=100, description="Идентификатор пользователя")
    session_id: Optional[str] = Field(None, min_length=1, max_length=100, description="Идентификатор сессии")
    platform: str = Field("web", description="Платформа (web, telegram, whatsapp, alice)")
    context: Optional[Dict[str, Any]] = Field(None, description="Дополнительный контекст")
    
    @validator('message')
    def validate_message(cls, v):
        """Валидация сообщения."""
        if not v or not v.strip():
            raise ValueError('Сообщение не может быть пустым')
        # Удаляем потенциально опасные символы
        cleaned = re.sub(r'[<>"]', '', v.strip())
        return cleaned
    
    @validator('platform')
    def validate_platform(cls, v):
        """Валидация платформы."""
        allowed_platforms = ['web', 'telegram', 'whatsapp', 'alice', 'vk']
        if v not in allowed_platforms:
            raise ValueError(f'Платформа должна быть одной из: {", ".join(allowed_platforms)}')
        return v
    
    @validator('user_id')
    def validate_user_id(cls, v):
        """Валидация user_id."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('user_id должен содержать только буквы, цифры, дефисы и подчеркивания')
        return v


class ChatResponse(BaseModel):
    """Ответ системы на сообщение."""
    message: str = Field(..., min_length=1, description="Ответ AI ассистента")
    session_id: str = Field(..., description="Идентификатор сессии")
    intent: Optional[str] = Field(None, description="Распознанное намерение")
    entities: Optional[Dict[str, Any]] = Field(None, description="Извлеченные сущности")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Уверенность в ответе")
    requires_human: bool = Field(False, description="Требуется ли вмешательство человека")
    suggested_actions: Optional[List[str]] = Field(None, description="Предлагаемые действия")
    
    @validator('confidence')
    def validate_confidence(cls, v):
        """Валидация уверенности."""
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError('Уверенность должна быть между 0.0 и 1.0')
        return v


@router.post("/chat", response_model=ChatResponse)
async def process_chat_message(
    request: ChatRequest,
    conversation_service: ConversationService = Depends(),
    nlp_service: NLPService = Depends()
) -> ChatResponse:
    """
    Обработка сообщения в чате с клиентом.
    
    Основной endpoint для взаимодействия с AI ассистентом.
    """
    try:
        # Генерируем session_id если не предоставлен
        session_id = request.session_id or str(uuid.uuid4())
        
        # Дополнительная валидация session_id
        if session_id and not re.match(r'^[a-zA-Z0-9_-]+$', session_id):
            raise HTTPException(
                status_code=400,
                detail="Некорректный формат session_id"
            )
        
        # Обрабатываем сообщение через NLP сервис
        nlp_result = await nlp_service.process_message(
            message=request.message,
            user_id=request.user_id,
            context=request.context
        )
        
        if not nlp_result:
            raise HTTPException(
                status_code=500,
                detail="Ошибка обработки NLP"
            )
        
        # Обрабатываем диалог через conversation сервис
        conversation_result = await conversation_service.process_conversation(
            user_id=request.user_id,
            session_id=session_id,
            message=request.message,
            intent=nlp_result.intent,
            entities=nlp_result.entities,
            platform=request.platform
        )
        
        if not conversation_result:
            raise HTTPException(
                status_code=500,
                detail="Ошибка обработки диалога"
            )
        
        return ChatResponse(
            message=conversation_result.response,
            session_id=session_id,
            intent=nlp_result.intent,
            entities=nlp_result.entities,
            confidence=nlp_result.confidence,
            requires_human=conversation_result.requires_human,
            suggested_actions=conversation_result.suggested_actions
        )
        
    except HTTPException:
        # Повторно выбрасываем HTTPException
        raise
    except ValueError as e:
        # Ошибки валидации
        raise HTTPException(
            status_code=400,
            detail=f"Ошибка валидации: {str(e)}"
        )
    except TimeoutError as e:
        # Таймауты
        raise HTTPException(
            status_code=504,
            detail="Превышено время ожидания обработки"
        )
    except Exception as e:
        # Общие ошибки
        import structlog
        logger = structlog.get_logger()
        logger.error("Неожиданная ошибка в process_chat_message", error=str(e), user_id=request.user_id)
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера"
        )


@router.get("/sessions/{user_id}", response_model=List[ConversationResponse])
async def get_user_sessions(
    user_id: str,
    conversation_service: ConversationService = Depends()
) -> List[ConversationResponse]:
    """Получить все сессии пользователя."""
    try:
        return await conversation_service.get_user_sessions(user_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения сессий: {str(e)}"
        )


@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    conversation_service: ConversationService = Depends()
) -> List[Dict[str, Any]]:
    """Получить историю сообщений в сессии."""
    try:
        return await conversation_service.get_session_history(session_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения истории: {str(e)}"
        )


@router.post("/sessions/{session_id}/escalate")
async def escalate_to_human(
    session_id: str,
    reason: str,
    conversation_service: ConversationService = Depends()
) -> Dict[str, str]:
    """Эскалация диалога к живому оператору."""
    try:
        result = await conversation_service.escalate_to_human(session_id, reason)
        return {"status": "escalated", "ticket_id": result.ticket_id}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка эскалации: {str(e)}"
        )