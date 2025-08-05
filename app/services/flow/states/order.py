"""Состояние обработки заказов."""
import random
import re
from typing import Any

from .base import ConversationState, StateContext, StateResult


class OrderState(ConversationState):
    """Состояние для работы с заказами - создание, отслеживание, изменение."""

    def __init__(self):
        super().__init__("order")

        # Паттерны для распознавания номеров заказов
        self.order_patterns = [
            r'\b(\d{6,12})\b',  # 6-12 цифр
            r'[№#]\s*(\d+)',     # № или # с цифрами
            r'заказ\s*(\d+)',    # "заказ 123456"
        ]

        # Паттерны для товаров
        self.product_patterns = {
            'electronics': ['телефон', 'смартфон', 'планшет', 'ноутбук', 'компьютер'],
            'clothing': ['футболка', 'джинсы', 'платье', 'куртка', 'обувь'],
            'books': ['книга', 'роман', 'учебник', 'словарь'],
            'home': ['мебель', 'посуда', 'декор', 'текстиль']
        }

    async def enter(self, context: StateContext) -> StateResult:
        """Вход в состояние обработки заказов."""
        self.logger.info("Вход в состояние обработки заказов")

        greeting = "Помогу вам с заказом! Что вас интересует - создать новый заказ или проверить существующий?"

        return StateResult(
            response=greeting,
            requires_input=True,
            suggested_actions=[
                "Создать новый заказ",
                "Проверить статус заказа",
                "Изменить заказ",
                "Отменить заказ"
            ]
        )

    async def handle_input(self, context: StateContext, message: str,
                          intent: str | None = None,
                          entities: dict[str, Any] | None = None) -> StateResult:
        """Обработка пользовательского ввода в состоянии заказа."""
        if not self.validate_input(message, intent):
            return StateResult(
                response="Не поняла ваш запрос. Что вы хотите сделать с заказом?",
                requires_input=True
            )

        message_lower = message.lower().strip()

        # Проверяем наличие номера заказа в сообщении
        order_number = self._extract_order_number(message)
        if order_number:
            context.add_entity("order_number", order_number)
            return await self._handle_order_inquiry(context, order_number)

        # Обработка различных намерений
        if intent == "create_order" or any(word in message_lower for word in ["создать", "оформить", "заказать", "купить"]):
            return await self._handle_create_order(context, message)

        elif intent == "check_order" or any(word in message_lower for word in ["проверить", "статус", "где заказ", "отследить"]):
            return await self._handle_check_order_request(context)

        elif intent == "modify_order" or any(word in message_lower for word in ["изменить", "поменять", "добавить к заказу"]):
            return await self._handle_modify_order(context, message)

        elif intent == "cancel_order" or any(word in message_lower for word in ["отменить", "аннулировать", "не нужен"]):
            return await self._handle_cancel_order(context, message)

        elif any(word in message_lower for word in ["доставка", "когда получу", "адрес"]):
            return StateResult(
                response="Вопросы доставки! Перехожу к специалисту по доставке.",
                next_state="shipping",
                should_continue=True
            )

        elif any(word in message_lower for word in ["оплата", "заплатить", "карта", "счет"]):
            return StateResult(
                response="Помогу с оплатой заказа!",
                next_state="payment",
                should_continue=True
            )

        else:
            return await self._handle_general_order_question(context, message)

    async def _handle_create_order(self, context: StateContext, message: str) -> StateResult:
        """Обработка создания нового заказа."""
        # Извлекаем товары из сообщения
        products = self._extract_products(message)
        if products:
            context.add_entity("requested_products", products)

            products_text = ", ".join(products)
            response = f"Отлично! Вы хотите заказать: {products_text}. Уточните количество и модель, если нужно."
        else:
            response = "Что именно вы хотите заказать? Назовите товар или услугу."

        return StateResult(
            response=response,
            requires_input=True,
            suggested_actions=[
                "Указать количество",
                "Выбрать модель",
                "Перейти к оформлению",
                "Посмотреть каталог"
            ]
        )

    async def _handle_check_order_request(self, context: StateContext) -> StateResult:
        """Обработка запроса проверки заказа."""
        # Проверяем, есть ли уже номер заказа в контексте
        order_number = context.get_entity("order_number")

        if order_number:
            return await self._handle_order_inquiry(context, order_number)
        else:
            return StateResult(
                response="Для проверки заказа назовите номер заказа. Он указан в SMS или email подтверждении.",
                requires_input=True,
                suggested_actions=[
                    "Ввести номер заказа",
                    "Найти по телефону",
                    "Найти по email"
                ]
            )

    async def _handle_order_inquiry(self, context: StateContext, order_number: str) -> StateResult:
        """Обработка запроса информации о заказе."""
        # TODO: Интеграция с реальной системой заказов
        # Пока что возвращаем mock данные

        mock_order_info = {
            "number": order_number,
            "status": "В обработке",
            "items": ["Смартфон Samsung Galaxy", "Чехол"],
            "total": 45000,
            "delivery_date": "15-17 марта"
        }

        response = f"""
Заказ №{order_number}:
📦 Статус: {mock_order_info['status']}
🛍️ Товары: {', '.join(str(item) for item in mock_order_info['items'])}
💰 Сумма: {mock_order_info['total']} руб.
🚚 Ожидаемая доставка: {mock_order_info['delivery_date']}

Нужна дополнительная информация?
        """.strip()

        return StateResult(
            response=response,
            requires_input=True,
            suggested_actions=[
                "Изменить адрес доставки",
                "Изменить товары",
                "Отменить заказ",
                "Связаться с курьером"
            ]
        )

    async def _handle_modify_order(self, context: StateContext, message: str) -> StateResult:
        """Обработка изменения заказа."""
        order_number = context.get_entity("order_number")

        if not order_number:
            return StateResult(
                response="Для изменения заказа сначала назовите номер заказа.",
                requires_input=True
            )

        # Анализируем, что хочет изменить пользователь
        if any(word in message.lower() for word in ["адрес", "доставка", "адрес доставки"]):
            return StateResult(
                response="Хотите изменить адрес доставки? Перехожу к специалисту по доставке.",
                next_state="shipping",
                should_continue=True
            )

        elif any(word in message.lower() for word in ["товар", "добавить", "убрать", "количество"]):
            return StateResult(
                response=f"Понято, хотите изменить состав заказа №{order_number}. Что именно изменить?",
                requires_input=True,
                suggested_actions=[
                    "Добавить товар",
                    "Убрать товар",
                    "Изменить количество",
                    "Заменить товар"
                ]
            )

        else:
            return StateResult(
                response="Что именно вы хотите изменить в заказе? Адрес доставки, товары или что-то еще?",
                requires_input=True
            )

    async def _handle_cancel_order(self, context: StateContext, message: str) -> StateResult:
        """Обработка отмены заказа."""
        order_number = context.get_entity("order_number")

        if not order_number:
            return StateResult(
                response="Для отмены заказа назовите номер заказа.",
                requires_input=True
            )

        # TODO: Реальная логика отмены заказа

        response = f"""
Заказ №{order_number} может быть отменен.

⚠️ Обратите внимание:
• Отмена возможна в течение 1 часа после оформления
• Если заказ уже в доставке, потребуется согласование
• Средства вернутся в течение 3-5 рабочих дней

Подтверждаете отмену?
        """.strip()

        return StateResult(
            response=response,
            requires_input=True,
            suggested_actions=[
                "Подтвердить отмену",
                "Отложить отмену",
                "Связаться с оператором"
            ]
        )

    async def _handle_general_order_question(self, context: StateContext, message: str) -> StateResult:
        """Обработка общих вопросов о заказах."""
        responses = [
            "По заказам я могу помочь с созданием, отслеживанием, изменением или отменой. Что вас интересует?",
            "Расскажите подробнee, что нужно сделать с заказом?",
            "Какой вопрос по заказу у вас возник?"
        ]

        return StateResult(
            response=random.choice(responses),
            requires_input=True,
            suggested_actions=[
                "Создать новый заказ",
                "Проверить статус заказа",
                "Изменить заказ",
                "Отменить заказ"
            ]
        )

    def _extract_order_number(self, message: str) -> str | None:
        """Извлечение номера заказа из сообщения."""
        for pattern in self.order_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_products(self, message: str) -> list[str]:
        """Извлечение названий товаров из сообщения."""
        found_products = []
        message_lower = message.lower()

        for _category, products in self.product_patterns.items():
            for product in products:
                if product in message_lower:
                    found_products.append(product)

        return found_products

    def get_available_actions(self, context: StateContext) -> list[str]:
        """Получить доступные действия в состоянии заказа."""
        base_actions = [
            "Создать новый заказ",
            "Проверить статус заказа",
            "Помощь с оформлением"
        ]

        # Если есть номер заказа, добавляем специфичные действия
        if context.has_entity("order_number"):
            base_actions.extend([
                "Изменить заказ",
                "Отменить заказ",
                "Связаться с курьером"
            ])

        return base_actions

    def can_transition_to(self, next_state: str) -> bool:
        """Проверить возможность перехода из состояния заказа."""
        allowed_transitions = ["shipping", "payment", "hello", "hangup"]
        return next_state in allowed_transitions
