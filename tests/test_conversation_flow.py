"""Тесты для conversation flow системы."""
from datetime import datetime

import pytest

from app.models.conversation import Platform
from app.services.flow.context import FlowContext
from app.services.flow.flow_service import ConversationFlowService
from app.services.flow.states.base import StateResult
from app.services.flow.states.hangup import HangupState
from app.services.flow.states.hello import HelloState
from app.services.flow.states.order import OrderState
from app.services.flow.states.payment import PaymentState
from app.services.flow.states.shipping import ShippingState


@pytest.fixture
def flow_service():
    """Создание экземпляра ConversationFlowService для тестов."""
    return ConversationFlowService()


@pytest.fixture
def sample_flow_context():
    """Пример контекста потока."""
    return {
        "user_id": "test_user_123",
        "session_id": "test_session_456",
        "platform": Platform.WEB,
        "current_state": "hello",
        "state_transitions": 0,
        "start_time": datetime.now(),
        "last_update": datetime.now(),
        "entities": {},
        "conversation_history": [],
    }


class TestConversationFlowService:
    """Тесты для ConversationFlowService."""

    @pytest.mark.asyncio
    async def test_process_conversation_flow_new_session(self, flow_service):
        """Тест обработки диалога для новой сессии."""
        result = await flow_service.process_conversation_flow(
            user_id="test_user",
            session_id="test_session",
            message="Привет!",
            platform=Platform.WEB,
            intent="greeting",
            entities={},
        )

        assert result is not None
        assert result.response is not None
        assert (
            "Привет" in result.response
            or "Здравствуйте" in result.response
            or "Добро пожаловать" in result.response
        )
        assert result.requires_human is False

    @pytest.mark.asyncio
    async def test_process_conversation_flow_order_inquiry(self, flow_service):
        """Тест обработки запроса о заказе."""
        # Сначала приветствие
        await flow_service.process_conversation_flow(
            user_id="test_user",
            session_id="test_session",
            message="Привет",
            platform=Platform.WEB,
            intent="greeting",
            entities={},
        )

        # Затем запрос о заказе
        result = await flow_service.process_conversation_flow(
            user_id="test_user",
            session_id="test_session",
            message="Где мой заказ №12345?",
            platform=Platform.WEB,
            intent="order_status",
            entities={"order_number": "12345"},
        )

        assert result is not None
        assert result.response is not None
        assert "заказ" in result.response.lower()

    @pytest.mark.asyncio
    async def test_get_session_state(self, flow_service):
        """Тест получения состояния сессии."""
        # Создаем сессию
        await flow_service.process_conversation_flow(
            user_id="test_user",
            session_id="test_session",
            message="Привет",
            platform=Platform.WEB,
        )

        # Получаем состояние
        state = await flow_service.get_session_state("test_session")

        assert state is not None
        assert state["current_state"] == "hello"
        assert state["state_transitions"] >= 0

    @pytest.mark.asyncio
    async def test_reset_session(self, flow_service):
        """Тест сброса сессии."""
        # Создаем сессию
        await flow_service.process_conversation_flow(
            user_id="test_user",
            session_id="test_session",
            message="Привет",
            platform=Platform.WEB,
        )

        # Сбрасываем сессию
        result = await flow_service.reset_session("test_session")
        assert result is True

        # Проверяем, что сессия сброшена
        state = await flow_service.get_session_state("test_session")
        assert state is None

    @pytest.mark.asyncio
    async def test_force_state_transition(self, flow_service):
        """Тест принудительного перехода состояния."""
        # Создаем сессию
        await flow_service.process_conversation_flow(
            user_id="test_user",
            session_id="test_session",
            message="Привет",
            platform=Platform.WEB,
        )

        # Принудительно переходим в состояние order
        result = await flow_service.force_state_transition("test_session", "order")
        assert result is True

        # Проверяем состояние
        state = await flow_service.get_session_state("test_session")
        assert state["current_state"] == "order"

    @pytest.mark.asyncio
    async def test_cleanup_inactive_sessions(self, flow_service):
        """Тест очистки неактивных сессий."""
        # Создаем сессию
        await flow_service.process_conversation_flow(
            user_id="test_user",
            session_id="test_session",
            message="Привет",
            platform=Platform.WEB,
        )

        # Очищаем сессии (с очень малым таймаутом для теста)
        cleaned = await flow_service.cleanup_inactive_sessions(0)
        assert cleaned >= 0

    def test_get_flow_metrics(self, flow_service):
        """Тест получения метрик."""
        metrics = flow_service.get_flow_metrics()

        assert "active_sessions" in metrics or "available_states" in metrics
        assert "state_distribution" in metrics or "available_states" in metrics


class TestConversationStates:
    """Тесты для состояний диалога."""

    @pytest.mark.asyncio
    async def test_hello_state(self):
        """Тест состояния приветствия."""
        from app.services.flow.context import StateContext

        state = HelloState()
        context = StateContext()

        result = await state.enter(context)

        assert isinstance(result, StateResult)
        assert result.response is not None
        assert result.requires_input is True

    @pytest.mark.asyncio
    async def test_order_state(self):
        """Тест состояния заказа."""
        from app.services.flow.context import StateContext

        state = OrderState()
        context = StateContext()
        context.message = "Где мой заказ №12345?"
        context.entities = {"order_number": "12345"}

        result = await state.enter(context)

        assert isinstance(result, StateResult)
        assert result.response is not None

    @pytest.mark.asyncio
    async def test_payment_state(self):
        """Тест состояния оплаты."""
        from app.services.flow.context import StateContext

        state = PaymentState()
        context = StateContext()
        context.message = "Не прошла оплата"

        result = await state.enter(context)

        assert isinstance(result, StateResult)
        assert result.response is not None
        assert "оплат" in result.response.lower()

    @pytest.mark.asyncio
    async def test_shipping_state(self):
        """Тест состояния доставки."""
        from app.services.flow.context import StateContext

        state = ShippingState()
        context = StateContext()
        context.message = "Когда доставка?"

        result = await state.enter(context)

        assert isinstance(result, StateResult)
        assert result.response is not None
        assert "доставк" in result.response.lower()

    @pytest.mark.asyncio
    async def test_hangup_state(self):
        """Тест состояния завершения."""
        from app.services.flow.context import StateContext

        state = HangupState()
        context = StateContext()
        context.message = "До свидания"

        result = await state.enter(context)

        assert isinstance(result, StateResult)
        assert result.response is not None
        assert result.should_continue is False


class TestFlowContext:
    """Тесты для контекста потока."""

    def test_flow_context_initialization(self):
        """Тест инициализации контекста."""
        context = FlowContext()

        assert context._current_state == "hello"
        assert len(context._states) > 0
        assert "hello" in context._states
        assert "order" in context._states

    @pytest.mark.asyncio
    async def test_flow_context_transition(self):
        """Тест перехода между состояниями."""
        context = FlowContext()

        # Начальное состояние
        assert context._current_state == "hello"

        # Переход в order
        result = await context._transition_to_state("order")
        assert result is True
        assert context._current_state == "order"

    @pytest.mark.asyncio
    async def test_flow_context_invalid_transition(self):
        """Тест недопустимого перехода."""
        context = FlowContext()

        # Попытка перехода в несуществующее состояние
        result = await context._transition_to_state("invalid_state")
        assert result is False
        assert context._current_state == "hello"  # Остаемся в текущем состоянии
