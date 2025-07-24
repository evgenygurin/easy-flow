"""
API endpoints для обработки диалогов с клиентами.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

from app.services.conversation_service import ConversationService
from app.services.nlp_service import NLPService
from app.models.conversation import ConversationCreate, ConversationResponse, MessageCreate

router = APIRouter()


class ChatRequest(BaseModel):
    """Запрос на обработку сообщения в чате."""
    message: str = Field(..., description="Текст сообщения от клиента")
    user_id: str = Field(..., description="Идентификатор пользователя")
    session_id: Optional[str] = Field(None, description="Идентификатор сессии")
    platform: str = Field("web", description="Платформа (web, telegram, whatsapp, alice)")
    context: Optional[Dict[str, Any]] = Field(None, description="Дополнительный контекст")


class ChatResponse(BaseModel):
    """Ответ системы на сообщение."""
    message: str = Field(..., description="Ответ AI ассистента")
    session_id: str = Field(..., description="Идентификатор сессии")
    intent: Optional[str] = Field(None, description="Распознанное намерение")
    entities: Optional[Dict[str, Any]] = Field(None, description="Извлеченные сущности")
    confidence: Optional[float] = Field(None, description="Уверенность в ответе")
    requires_human: bool = Field(False, description="Требуется ли вмешательство человека")
    suggested_actions: Optional[List[str]] = Field(None, description="Предлагаемые действия")


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
        
        # Обрабатываем сообщение через NLP сервис
        nlp_result = await nlp_service.process_message(
            message=request.message,
            user_id=request.user_id,
            context=request.context
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
        
        return ChatResponse(
            message=conversation_result.response,
            session_id=session_id,
            intent=nlp_result.intent,
            entities=nlp_result.entities,
            confidence=nlp_result.confidence,
            requires_human=conversation_result.requires_human,
            suggested_actions=conversation_result.suggested_actions
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка обработки сообщения: {str(e)}"
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