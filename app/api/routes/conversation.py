"""API endpoints для обработки диалогов с клиентами."""
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.api.dependencies import get_conversation_service
from app.models.conversation import ConversationResponse, Platform
from app.services.conversation_service import ConversationService
from app.services.nlp_service import NLPService


router = APIRouter()


class ChatRequest(BaseModel):
    """Запрос на обработку сообщения в чате."""

    message: str = Field(..., min_length=1, max_length=4000, description="Текст сообщения от клиента")
    user_id: str = Field(..., min_length=1, max_length=100, description="Идентификатор пользователя")
    session_id: str | None = Field(None, min_length=1, max_length=100, description="Идентификатор сессии")
    platform: str = Field("web", description="Платформа (web, telegram, whatsapp, alice)")
    context: dict[str, Any] | None = Field(None, description="Дополнительный контекст")

    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Валидация сообщения."""
        if not v or not v.strip():
            raise ValueError('Сообщение не может быть пустым')
        # Удаляем потенциально опасные символы
        cleaned = re.sub(r'[<>"]', '', v.strip())
        return cleaned

    @field_validator('platform')
    @classmethod
    def validate_platform(cls, v: str) -> str:
        """Валидация платформы."""
        allowed_platforms = ['web', 'telegram', 'whatsapp', 'alice', 'vk']
        if v not in allowed_platforms:
            raise ValueError(f'Платформа должна быть одной из: {", ".join(allowed_platforms)}')
        return v

    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Валидация user_id."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('user_id должен содержать только буквы, цифры, дефисы и подчеркивания')
        return v


class ChatResponse(BaseModel):
    """Ответ системы на сообщение."""

    message: str = Field(..., min_length=1, description="Ответ AI ассистента")
    session_id: str = Field(..., description="Идентификатор сессии")
    intent: str | None = Field(None, description="Распознанное намерение")
    entities: dict[str, Any] | None = Field(None, description="Извлеченные сущности")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Уверенность в ответе")
    requires_human: bool = Field(False, description="Требуется ли вмешательство человека")
    suggested_actions: list[str] | None = Field(None, description="Предлагаемые действия")

    # Информация о conversation flow
    current_state: str | None = Field(None, description="Текущее состояние диалога")
    state_transitions: int | None = Field(None, description="Количество переходов между состояниями")

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float | None) -> float | None:
        """Валидация уверенности."""
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError('Уверенность должна быть между 0.0 и 1.0')
        return v


@router.post("/chat", response_model=ChatResponse)
async def process_chat_message(
    request: ChatRequest,
    conversation_service: ConversationService = Depends(get_conversation_service),
    nlp_service: NLPService = Depends()
) -> ChatResponse:
    """Обработка сообщения в чате с клиентом.

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
            platform=Platform(request.platform)
        )

        if not conversation_result:
            raise HTTPException(
                status_code=500,
                detail="Ошибка обработки диалога"
            )

        # Получаем информацию о состоянии conversation flow
        flow_state = await conversation_service.get_flow_session_state(session_id)
        current_state = flow_state.get("current_state") if flow_state else None
        state_transitions = flow_state.get("state_transitions") if flow_state else None
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

    except HTTPException:
        # Повторно выбрасываем HTTPException
        raise
    except ValueError as e:
        # Ошибки валидации
        raise HTTPException(
            status_code=400,
            detail=f"Ошибка валидации: {str(e)}"
        )
    except TimeoutError:
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


@router.get("/sessions/{user_id}", response_model=list[ConversationResponse])
async def get_user_sessions(
    user_id: str,
    conversation_service: ConversationService = Depends()
) -> list[ConversationResponse]:
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
) -> list[dict[str, Any]]:
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
) -> dict[str, str]:
    """Эскалация диалога к живому оператору."""
    try:
        result = await conversation_service.escalate_to_human(session_id, reason)
        return {"status": "escalated", "ticket_id": result.ticket_id}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка эскалации: {str(e)}"
        )


# Conversation Flow Management Endpoints

@router.get("/flow/sessions/{session_id}/state")
async def get_flow_session_state(
    session_id: str,
    conversation_service: ConversationService = Depends()
) -> dict[str, Any]:
    """Получить состояние conversation flow сессии."""
    try:
        state = await conversation_service.get_flow_session_state(session_id)
        if not state:
            raise HTTPException(
                status_code=404,
                detail="Сессия не найдена"
            )
        return state
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения состояния сессии: {str(e)}"
        ) from e


@router.post("/flow/sessions/{session_id}/reset")
async def reset_flow_session(
    session_id: str,
    conversation_service: ConversationService = Depends()
) -> dict[str, str]:
    """Сбросить conversation flow сессию."""
    try:
        success = await conversation_service.reset_flow_session(session_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Сессия не найдена"
            )
        return {"status": "reset", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка сброса сессии: {str(e)}"
        ) from e


class StateTransitionRequest(BaseModel):
    """Запрос на принудительный переход состояния."""

    state_name: str = Field(..., description="Название целевого состояния")
    reason: str | None = Field(None, description="Причина принудительного перехода")


@router.post("/flow/sessions/{session_id}/transition")
async def force_flow_state_transition(
    session_id: str,
    request: StateTransitionRequest,
    conversation_service: ConversationService = Depends()
) -> dict[str, str]:
    """Принудительный переход в состояние conversation flow."""
    try:
        success = await conversation_service.force_flow_state_transition(
            session_id, request.state_name
        )
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Не удалось выполнить переход состояния"
            )
        return {
            "status": "transitioned",
            "session_id": session_id,
            "new_state": request.state_name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка перехода состояния: {str(e)}"
        ) from e


@router.get("/flow/metrics")
async def get_flow_metrics(
    conversation_service: ConversationService = Depends()
) -> dict[str, Any]:
    """Получить метрики conversation flow."""
    try:
        metrics = conversation_service.get_flow_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения метрик: {str(e)}"
        ) from e


class CleanupRequest(BaseModel):
    """Запрос на очистку неактивных сессий."""

    max_inactive_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Максимальное время неактивности в минутах (1-1440)"
    )


@router.post("/flow/cleanup")
async def cleanup_inactive_flow_sessions(
    request: CleanupRequest,
    conversation_service: ConversationService = Depends()
) -> dict[str, int]:
    """Очистка неактивных conversation flow сессий."""
    try:
        cleaned_count = await conversation_service.cleanup_inactive_flow_sessions(
            request.max_inactive_minutes
        )
        return {
            "cleaned_sessions": cleaned_count,
            "max_inactive_minutes": request.max_inactive_minutes
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка очистки сессий: {str(e)}"
        ) from e
