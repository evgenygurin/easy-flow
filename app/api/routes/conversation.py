"""API endpoints для обработки диалогов с клиентами."""
from typing import Any

from fastapi import APIRouter, Depends

from app.api.controllers.conversation_controller import (
    ChatRequest,
    ChatResponse,
    CleanupRequest,
    ConversationController,
    StateTransitionRequest
)
from app.api.dependencies import get_conversation_controller
from app.models.conversation import ConversationResponse


router = APIRouter()




@router.post("/chat", response_model=ChatResponse)
async def process_chat_message(
    request: ChatRequest,
    controller: ConversationController = Depends(get_conversation_controller)
) -> ChatResponse:
    """Обработка сообщения в чате с клиентом.

    Основной endpoint для взаимодействия с AI ассистентом.
    """
    return await controller.process_chat_message(request)


@router.get("/sessions/{user_id}", response_model=list[ConversationResponse])
async def get_user_sessions(
    user_id: str,
    controller: ConversationController = Depends(get_conversation_controller)
) -> list[ConversationResponse]:
    """Получить все сессии пользователя."""
    return await controller.get_user_sessions(user_id)


@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    controller: ConversationController = Depends(get_conversation_controller)
) -> list[dict[str, Any]]:
    """Получить историю сообщений в сессии."""
    return await controller.get_session_history(session_id)


@router.post("/sessions/{session_id}/escalate")
async def escalate_to_human(
    session_id: str,
    reason: str,
    controller: ConversationController = Depends(get_conversation_controller)
) -> dict[str, str]:
    """Эскалация диалога к живому оператору."""
    return await controller.escalate_to_human(session_id, reason)


# Conversation Flow Management Endpoints

@router.get("/flow/sessions/{session_id}/state")
async def get_flow_session_state(
    session_id: str,
    controller: ConversationController = Depends(get_conversation_controller)
) -> dict[str, Any]:
    """Получить состояние conversation flow сессии."""
    return await controller.get_flow_session_state(session_id)


@router.post("/flow/sessions/{session_id}/reset")
async def reset_flow_session(
    session_id: str,
    controller: ConversationController = Depends(get_conversation_controller)
) -> dict[str, str]:
    """Сбросить conversation flow сессию."""
    return await controller.reset_flow_session(session_id)




@router.post("/flow/sessions/{session_id}/transition")
async def force_flow_state_transition(
    session_id: str,
    request: StateTransitionRequest,
    controller: ConversationController = Depends(get_conversation_controller)
) -> dict[str, str]:
    """Принудительный переход в состояние conversation flow."""
    return await controller.force_flow_state_transition(session_id, request)


@router.get("/flow/metrics")
async def get_flow_metrics(
    controller: ConversationController = Depends(get_conversation_controller)
) -> dict[str, Any]:
    """Получить метрики conversation flow."""
    return await controller.get_flow_metrics()




@router.post("/flow/cleanup")
async def cleanup_inactive_flow_sessions(
    request: CleanupRequest,
    controller: ConversationController = Depends(get_conversation_controller)
) -> dict[str, int]:
    """Очистка неактивных conversation flow сессий."""
    return await controller.cleanup_inactive_flow_sessions(request)
