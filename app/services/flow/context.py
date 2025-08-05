"""Контекст для управления состояниями conversation flow."""

import structlog

from app.models.conversation import Platform

from .states import HangupState, HelloState, OrderState, PaymentState, ShippingState
from .states.base import ConversationState, StateContext, StateResult


logger = structlog.get_logger()


class FlowContext:
    """Менеджер контекста conversation flow."""

    def __init__(self):
        # Регистрируем доступные состояния
        self._states: dict[str, type[ConversationState]] = {
            "hello": HelloState,
            "order": OrderState,
            "payment": PaymentState,
            "shipping": ShippingState,
            "hangup": HangupState
        }

        # Активные контексты сессий
        self._session_contexts: dict[str, StateContext] = {}

        self.logger = logger.bind(component="flow_context")

    async def process_message(
        self,
        user_id: str,
        session_id: str,
        message: str,
        platform: Platform,
        intent: str | None = None,
        entities: dict | None = None
    ) -> StateResult:
        """Обработка сообщения через state machine.

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
            StateResult: Результат обработки
        """
        try:
            # Получаем или создаем контекст сессии
            context = await self._get_or_create_context(user_id, session_id, platform)

            # Если текущего состояния нет, начинаем с приветствия
            if not context.current_state:
                await self._transition_to_state(context, "hello")

            # Обрабатываем сообщение в текущем состоянии
            result = await context.current_state.handle_input(
                context, message, intent, entities
            )

            # Если нужен переход в другое состояние
            if result.next_state:
                await self._transition_to_state(context, result.next_state)

            # Сохраняем обновленный контекст
            self._session_contexts[session_id] = context

            self.logger.info(
                "Сообщение обработано",
                user_id=user_id,
                session_id=session_id,
                current_state=context.current_state.name if context.current_state else None,
                next_state=result.next_state
            )

            return result

        except Exception as e:
            self.logger.error(
                "Ошибка обработки сообщения в flow",
                error=str(e),
                user_id=user_id,
                session_id=session_id
            )

            # Возвращаем fallback результат
            return StateResult(
                response="Извините, произошла ошибка. Попробуйте еще раз.",
                next_state="hello",
                should_continue=True
            )

    async def _get_or_create_context(
        self,
        user_id: str,
        session_id: str,
        platform: Platform
    ) -> StateContext:
        """Получить или создать контекст сессии."""
        if session_id in self._session_contexts:
            context = self._session_contexts[session_id]
            # Обновляем время последней активности
            context.last_activity = context.last_activity.__class__.now()
            return context

        # Создаем новый контекст
        context = StateContext(user_id, session_id, platform)
        self._session_contexts[session_id] = context

        self.logger.info(
            "Создан новый контекст сессии",
            user_id=user_id,
            session_id=session_id,
            platform=platform.value
        )

        return context

    async def _transition_to_state(self, context: StateContext, state_name: str) -> None:
        """Переход в новое состояние."""
        if state_name not in self._states:
            self.logger.error(f"Неизвестное состояние: {state_name}")
            state_name = "hello"  # Fallback на hello

        # Проверяем возможность перехода
        if context.current_state and not context.current_state.can_transition_to(state_name):
            self.logger.warning(
                "Переход запрещен",
                from_state=context.current_state.name,
                to_state=state_name
            )
            return

        # Выходим из текущего состояния
        if context.current_state:
            await context.current_state.exit(context)

        # Создаем новое состояние
        new_state = self._states[state_name]()
        context.set_state(new_state)

        # Входим в новое состояние
        await new_state.enter(context)

        self.logger.info(
            "Переход в состояние выполнен",
            session_id=context.session_id,
            new_state=state_name
        )

    def get_session_context(self, session_id: str) -> StateContext | None:
        """Получить контекст сессии."""
        return self._session_contexts.get(session_id)

    def get_active_sessions_count(self) -> int:
        """Получить количество активных сессий."""
        return len(self._session_contexts)

    def cleanup_inactive_sessions(self, max_inactive_minutes: int = 30) -> int:
        """Очистка неактивных сессий."""
        from datetime import datetime, timedelta

        cutoff_time = datetime.now() - timedelta(minutes=max_inactive_minutes)
        inactive_sessions = []

        for session_id, context in self._session_contexts.items():
            if context.last_activity < cutoff_time:
                inactive_sessions.append(session_id)

        # Удаляем неактивные сессии
        for session_id in inactive_sessions:
            del self._session_contexts[session_id]

        if inactive_sessions:
            self.logger.info(
                "Очищены неактивные сессии",
                count=len(inactive_sessions)
            )

        return len(inactive_sessions)

    def reset_session(self, session_id: str) -> bool:
        """Сброс контекста сессии."""
        if session_id in self._session_contexts:
            context = self._session_contexts[session_id]
            context.reset_context()

            self.logger.info("Контекст сессии сброшен", session_id=session_id)
            return True

        return False

    def get_session_metrics(self, session_id: str) -> dict | None:
        """Получить метрики сессии."""
        context = self._session_contexts.get(session_id)
        if not context:
            return None

        return {
            "message_count": context.message_count,
            "state_transitions": context.state_transitions,
            "current_state": context.current_state.name if context.current_state else None,
            "session_duration_minutes": (
                context.last_activity - context.created_at
            ).total_seconds() / 60,
            "extracted_entities_count": len(context.extracted_entities),
            "should_escalate": context.should_escalate()
        }

    def get_available_states(self) -> list[str]:
        """Получить список доступных состояний."""
        return list(self._states.keys())

    async def force_transition(self, session_id: str, state_name: str) -> bool:
        """Принудительный переход в состояние (для админских целей)."""
        context = self._session_contexts.get(session_id)
        if not context:
            return False

        try:
            await self._transition_to_state(context, state_name)
            return True
        except Exception as e:
            self.logger.error(
                "Ошибка принудительного перехода",
                error=str(e),
                session_id=session_id,
                target_state=state_name
            )
            return False
