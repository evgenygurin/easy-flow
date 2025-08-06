"""Основной сервис conversation flow."""
from typing import Any

import structlog

from app.models.conversation import ConversationResult, Platform

from .context import FlowContext


logger = structlog.get_logger()


class ConversationFlowService:
    """Сервис для управления conversation flow."""

    def __init__(self):
        self.flow_context = FlowContext()
        self.logger = logger.bind(service="conversation_flow")

    async def process_conversation_flow(
        self,
        user_id: str,
        session_id: str,
        message: str,
        platform: Platform,
        intent: str | None = None,
        entities: dict[str, Any] | None = None
    ) -> ConversationResult:
        """Обработка сообщения через conversation flow.

        Args:
        ----
            user_id: ID пользователя
            session_id: ID сессии
            message: Текст сообщения
            platform: Платформа
            intent: Распознанное намерение
            entities: Извлеченные сущности

        Returns:
        -------
            ConversationResult: Результат обработки

        """
        try:
            self.logger.info(
                "Обработка через conversation flow",
                user_id=user_id,
                session_id=session_id,
                intent=intent,
                platform=platform.value
            )

            # Обрабатываем сообщение через flow контекст
            state_result = await self.flow_context.process_message(
                user_id=user_id,
                session_id=session_id,
                message=message,
                platform=platform,
                intent=intent,
                entities=entities
            )

            # Проверяем необходимость эскалации
            requires_human = self._should_escalate(state_result, session_id)
            escalation_reason = None

            if requires_human:
                escalation_reason = self._determine_escalation_reason(state_result, session_id)

            # Формируем результат
            result = ConversationResult(
                response=state_result.response,
                requires_human=requires_human,
                suggested_actions=state_result.suggested_actions,
                next_questions=self._generate_next_questions(state_result, session_id),
                escalation_reason=escalation_reason
            )

            self.logger.info(
                "Conversation flow обработан",
                session_id=session_id,
                requires_human=requires_human,
                escalation_reason=escalation_reason
            )

            return result

        except Exception as e:
            self.logger.error(
                "Ошибка в conversation flow",
                error=str(e),
                user_id=user_id,
                session_id=session_id
            )

            # Возвращаем fallback результат
            return ConversationResult(
                response="Извините, произошла ошибка. Попробуйте переформулировать вопрос.",
                requires_human=True,
                suggested_actions=None,
                next_questions=None,
                escalation_reason="system_error"
            )

    def _should_escalate(self, state_result, session_id: str) -> bool:
        """Определить необходимость эскалации."""
        # Если в метаданных состояния указана эскалация
        if state_result.metadata and state_result.metadata.get("escalated_to_human"):
            return True

        # Проверяем контекст сессии
        context = self.flow_context.get_session_context(session_id)
        if context and context.should_escalate():
            return True

        # Если диалог завершен без разрешения проблемы
        if not state_result.should_continue and state_result.metadata:
            escalation_reason = state_result.metadata.get("escalation_reason")
            if escalation_reason in ["complaint", "complex_issue", "technical_issue"]:
                return True

        return False

    def _determine_escalation_reason(self, state_result, session_id: str) -> str | None:
        """Определить причину эскалации."""
        # Из метаданных состояния
        if state_result.metadata:
            reason = state_result.metadata.get("escalation_reason")
            if reason:
                return reason

        # Из контекста сессии
        context = self.flow_context.get_session_context(session_id)
        if context:
            # Длинная conversation без прогресса
            if context.message_count > 15:
                return "long_conversation"

            # Зацикливание между состояниями
            if len(context.state_history) > 8:
                recent_states = context.state_history[-4:]
                if len(set(recent_states)) <= 2:
                    return "conversation_loop"

            # Текущий интент требует человека
            if context.current_intent in ["complaint", "refund_request", "technical_issue"]:
                return context.current_intent

        return "general"

    def _generate_next_questions(self, state_result, session_id: str) -> list[str] | None:
        """Генерация следующих вопросов на основе контекста."""
        context = self.flow_context.get_session_context(session_id)
        if not context or not context.current_state:
            return None

        # Получаем доступные действия из текущего состояния
        available_actions = context.current_state.get_available_actions(context)

        # Преобразуем действия в вопросы
        questions = []
        for action in available_actions[:3]:  # Берем первые 3
            if "создать" in action.lower():
                questions.append("Хотите создать новый заказ?")
            elif "проверить" in action.lower():
                questions.append("Нужно проверить статус заказа?")
            elif "изменить" in action.lower():
                questions.append("Требуется что-то изменить?")
            elif "связаться" in action.lower():
                questions.append("Нужна помощь оператора?")

        return questions if questions else None

    async def get_session_state(self, session_id: str) -> dict[str, Any] | None:
        """Получить текущее состояние сессии."""
        context = self.flow_context.get_session_context(session_id)
        if not context:
            return None

        return {
            "current_state": context.current_state.name if context.current_state else None,
            "user_id": context.user_id,
            "platform": context.platform.value,
            "message_count": context.message_count,
            "state_transitions": context.state_transitions,
            "extracted_entities": context.extracted_entities,
            "should_escalate": context.should_escalate(),
            "last_activity": context.last_activity.isoformat(),
            "available_actions": (
                context.current_state.get_available_actions(context)
                if context.current_state else []
            )
        }

    async def reset_session(self, session_id: str) -> bool:
        """Сброс сессии (начать заново)."""
        return self.flow_context.reset_session(session_id)

    async def force_state_transition(self, session_id: str, state_name: str) -> bool:
        """Принудительный переход в состояние (для админов)."""
        return await self.flow_context.force_transition(session_id, state_name)

    def get_flow_metrics(self) -> dict[str, Any]:
        """Получить метрики conversation flow."""
        active_sessions = self.flow_context.get_active_sessions_count()

        # Собираем статистику по состояниям
        state_distribution = {}
        escalation_count = 0

        for session_id in self.flow_context._session_contexts:
            context = self.flow_context.get_session_context(session_id)
            if context and context.current_state:
                state_name = context.current_state.name
                state_distribution[state_name] = state_distribution.get(state_name, 0) + 1

                if context.should_escalate():
                    escalation_count += 1

        return {
            "active_sessions": active_sessions,
            "state_distribution": state_distribution,
            "sessions_requiring_escalation": escalation_count,
            "available_states": self.flow_context.get_available_states()
        }

    async def cleanup_inactive_sessions(self, max_inactive_minutes: int = 30) -> int:
        """Очистка неактивных сессий."""
        return self.flow_context.cleanup_inactive_sessions(max_inactive_minutes)
