"""Состояние приветствия пользователя."""
import random
from typing import Any

from .base import ConversationState, StateContext, StateResult


class HelloState(ConversationState):
    """Состояние приветствия и первичной идентификации пользователя."""

    def __init__(self):
        super().__init__("hello")
        self.greeting_messages = [
            "Здравствуйте! Меня зовут Анна, я ваш виртуальный помощник. Как дела?",
            "Добро пожаловать! Я помогу вам с любыми вопросами. Как поживаете?",
            "Привет! Рада вас видеть. Чем могу помочь?",
            "Здравствуйте! Как ваши дела? Готова помочь с любыми вопросами."
        ]

        self.returning_user_messages = [
            "Рада снова вас видеть! Как дела?",
            "Привет! Мы уже знакомы. Чем могу помочь сегодня?",
            "Здравствуйте! Приятно встретиться снова. Как поживаете?"
        ]

    async def enter(self, context: StateContext) -> StateResult:
        """Вход в состояние приветствия."""
        self.logger.info("Вход в состояние приветствия")

        # Проверяем, новый ли это пользователь
        is_returning = context.get_user_preference("is_returning_user", False)

        if is_returning:
            greeting = random.choice(self.returning_user_messages)
        else:
            greeting = random.choice(self.greeting_messages)
            context.set_user_preference("is_returning_user", True)

        return StateResult(
            response=greeting,
            requires_input=True,
            suggested_actions=[
                "Узнать о товарах",
                "Проверить заказ",
                "Связаться с оператором",
                "Помощь"
            ]
        )

    async def handle_input(self, context: StateContext, message: str,
                          intent: str | None = None,
                          entities: dict[str, Any] | None = None) -> StateResult:
        """Обработка пользовательского ввода в состоянии приветствия."""
        if not self.validate_input(message, intent):
            return StateResult(
                response="Извините, я не поняла. Можете переформулировать?",
                requires_input=True
            )

        message_lower = message.lower().strip()

        # Обработка различных интентов
        if intent == "greeting" or any(word in message_lower for word in ["привет", "здравствуй", "добро пожаловать"]):
            return await self._handle_greeting(context, message)

        elif intent == "order_inquiry" or any(word in message_lower for word in ["заказ", "заказать", "купить"]):
            return StateResult(
                response="Отлично! Помогу вам с заказом. Что вас интересует?",
                next_state="order",
                should_continue=True
            )

        elif intent == "shipping_inquiry" or any(word in message_lower for word in ["доставка", "доставить", "когда получу"]):
            return StateResult(
                response="Расскажу о доставке. Давайте уточним детали.",
                next_state="shipping",
                should_continue=True
            )

        elif intent == "payment_inquiry" or any(word in message_lower for word in ["оплата", "заплатить", "карта"]):
            return StateResult(
                response="Помогу с оплатой. Какой способ оплаты вас интересует?",
                next_state="payment",
                should_continue=True
            )

        elif intent == "complaint" or any(word in message_lower for word in ["жалоба", "проблема", "не работает"]):
            return StateResult(
                response="Понимаю, что у вас возникла проблема. Соединяю с оператором.",
                next_state="hangup",
                should_continue=False,
                metadata={"escalation_reason": "complaint"}
            )

        elif intent == "help" or any(word in message_lower for word in ["помощь", "помоги", "не понимаю"]):
            return await self._handle_help_request(context)

        elif any(word in message_lower for word in ["спасибо", "благодарю", "хорошо", "отлично"]):
            return StateResult(
                response="Пожалуйста! Чем еще могу помочь?",
                requires_input=True,
                suggested_actions=["Узнать о товарах", "Проверить заказ", "Помощь"]
            )

        else:
            # Общий ответ для неизвестных запросов
            return await self._handle_unknown_input(context, message)

    async def _handle_greeting(self, context: StateContext, message: str) -> StateResult:
        """Обработка приветствия."""
        responses = [
            "Привет! Рада общению. Чем могу быть полезна?",
            "Здравствуйте! Готова помочь. Что вас интересует?",
            "Привет! Как дела? Чем займемся?"
        ]

        return StateResult(
            response=random.choice(responses),
            requires_input=True,
            suggested_actions=["Узнать о товарах", "Проверить заказ", "Помощь"]
        )

    async def _handle_help_request(self, context: StateContext) -> StateResult:
        """Обработка запроса помощи."""
        help_text = """
Я могу помочь вам с:
• Информацией о товарах и услугах
• Оформлением и отслеживанием заказов
• Вопросами доставки и оплаты
• Связью с оператором при необходимости

Просто скажите, что вас интересует!
        """.strip()

        return StateResult(
            response=help_text,
            requires_input=True,
            suggested_actions=[
                "Узнать о товарах",
                "Проверить заказ",
                "Вопросы доставки",
                "Связаться с оператором"
            ]
        )

    async def _handle_unknown_input(self, context: StateContext, message: str) -> StateResult:
        """Обработка неизвестного ввода."""
        # Сохраняем неизвестный запрос для анализа
        context.add_entity("unknown_request", message)

        responses = [
            "Интересный вопрос! Можете рассказать подробнее?",
            "Давайте разберемся. Что именно вас интересует?",
            "Хм, не совсем поняла. Уточните, пожалуйста, чем могу помочь?"
        ]

        return StateResult(
            response=random.choice(responses),
            requires_input=True,
            suggested_actions=[
                "Узнать о товарах",
                "Проверить заказ",
                "Связаться с оператором",
                "Помощь"
            ]
        )

    def get_available_actions(self, context: StateContext) -> list[str]:
        """Получить доступные действия в состоянии приветствия."""
        return [
            "Узнать о товарах",
            "Проверить заказ",
            "Вопросы доставки",
            "Помощь с оплатой",
            "Связаться с оператором"
        ]

    def can_transition_to(self, next_state: str) -> bool:
        """Проверить возможность перехода из состояния приветствия."""
        allowed_transitions = ["order", "shipping", "payment", "hangup"]
        return next_state in allowed_transitions
