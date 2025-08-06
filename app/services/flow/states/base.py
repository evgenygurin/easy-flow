"""Базовые классы для системы состояний conversation flow."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog

from app.models.conversation import MessageResponse, Platform


logger = structlog.get_logger()


@dataclass
class StateResult:
    """Результат выполнения состояния."""

    response: str
    next_state: str | None = None
    should_continue: bool = True
    requires_input: bool = True
    suggested_actions: list[str] | None = None
    metadata: dict[str, Any] | None = None


class ConversationState(ABC):
    """Базовый класс для состояний диалога."""

    def __init__(self, name: str):
        self.name = name
        self.created_at = datetime.now()
        self.logger = logger.bind(state=name)

    @abstractmethod
    async def enter(self, context: "StateContext") -> StateResult:
        """Вход в состояние.

        Args:
        ----
            context: Контекст состояния

        Returns:
        -------
            StateResult: Результат входа в состояние

        """

    @abstractmethod
    async def handle_input(self, context: "StateContext", message: str,
                          intent: str | None = None,
                          entities: dict[str, Any] | None = None) -> StateResult:
        """Обработка пользовательского ввода в состоянии.

        Args:
        ----
            context: Контекст состояния
            message: Сообщение пользователя
            intent: Распознанное намерение
            entities: Извлеченные сущности

        Returns:
        -------
            StateResult: Результат обработки

        """

    async def exit(self, context: "StateContext") -> None:
        """Выход из состояния.

        Args:
        ----
            context: Контекст состояния

        """
        self.logger.info("Выход из состояния", state=self.name)

    def can_transition_to(self, next_state: str) -> bool:
        """Проверить возможность перехода в следующее состояние.

        Args:
        ----
            next_state: Название следующего состояния

        Returns:
        -------
            bool: Возможен ли переход

        """
        return True  # По умолчанию разрешены все переходы

    def get_available_actions(self, context: "StateContext") -> list[str]:
        """Получить доступные действия в текущем состоянии.

        Args:
        ----
            context: Контекст состояния

        Returns:
        -------
            List[str]: Список доступных действий

        """
        return []

    def validate_input(self, message: str, intent: str | None = None) -> bool:
        """Валидация пользовательского ввода.

        Args:
        ----
            message: Сообщение пользователя
            intent: Распознанное намерение

        Returns:
        -------
            bool: Валиден ли ввод

        """
        return bool(message and message.strip())


class StateContext:
    """Контекст для управления состояниями диалога."""

    def __init__(self, user_id: str, session_id: str, platform: Platform):
        self.user_id = user_id
        self.session_id = session_id
        self.platform = platform

        # Состояние
        self.current_state: ConversationState | None = None
        self.previous_state: str | None = None
        self.state_history: list[str] = []

        # Данные
        self.conversation_history: list[MessageResponse] = []
        self.user_data: dict[str, Any] = {}
        self.session_data: dict[str, Any] = {}
        self.extracted_entities: dict[str, Any] = {}

        # Метрики
        self.message_count = 0
        self.state_transitions = 0
        self.created_at = datetime.now()
        self.last_activity = datetime.now()

        self.logger = logger.bind(
            user_id=user_id,
            session_id=session_id,
            platform=platform.value
        )

    def add_message(self, message: MessageResponse) -> None:
        """Добавить сообщение в историю."""
        self.conversation_history.append(message)
        self.message_count += 1
        self.last_activity = datetime.now()

    def set_state(self, state: ConversationState) -> None:
        """Установить новое состояние."""
        if self.current_state:
            self.previous_state = self.current_state.name
            self.state_history.append(self.current_state.name)

        self.current_state = state
        self.state_transitions += 1
        self.last_activity = datetime.now()

        self.logger.info(
            "Переход в новое состояние",
            new_state=state.name,
            previous_state=self.previous_state
        )

    def get_user_preference(self, key: str, default: Any = None) -> Any:
        """Получить пользовательскую настройку."""
        return self.user_data.get(key, default)

    def set_user_preference(self, key: str, value: Any) -> None:
        """Установить пользовательскую настройку."""
        self.user_data[key] = value

    def get_session_data(self, key: str, default: Any = None) -> Any:
        """Получить данные сессии."""
        return self.session_data.get(key, default)

    def set_session_data(self, key: str, value: Any) -> None:
        """Установить данные сессии."""
        self.session_data[key] = value

    def add_entity(self, key: str, value: Any) -> None:
        """Добавить извлеченную сущность."""
        self.extracted_entities[key] = value

    def get_entity(self, key: str, default: Any = None) -> Any:
        """Получить извлеченную сущность."""
        return self.extracted_entities.get(key, default)

    def has_entity(self, key: str) -> bool:
        """Проверить наличие сущности."""
        return key in self.extracted_entities

    def should_escalate(self) -> bool:
        """Определить необходимость эскалации."""
        # Много сообщений без прогресса
        if self.message_count > 15:
            return True

        # Зацикливание между состояниями
        if len(self.state_history) > 10:
            recent_states = self.state_history[-6:]
            if len(set(recent_states)) <= 2:
                return True

        return False

    def reset_context(self) -> None:
        """Сброс контекста (новая сессия)."""
        self.conversation_history.clear()
        self.user_data.clear()
        self.session_data.clear()
        self.extracted_entities.clear()
        self.state_history.clear()

        self.message_count = 0
        self.state_transitions = 0
        self.current_state = None
        self.previous_state = None
        self.last_activity = datetime.now()
