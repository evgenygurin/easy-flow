"""Состояние обработки доставки."""
import random
import re
from typing import Any

from .base import ConversationState, StateContext, StateResult


class ShippingState(ConversationState):
    """Состояние для работы с доставкой - информация, изменение адреса, отслеживание."""

    def __init__(self):
        super().__init__("shipping")

        # Паттерны для адресов
        self.address_patterns = [
            r'г\.\s*([^\s,]+)',  # г. Москва
            r'город\s+([^\s,]+)',  # город Москва
            r'ул\.\s*([^,\d]+)',  # ул. Ленина
            r'улица\s+([^,\d]+)',  # улица Ленина
            r'д\.\s*(\d+)',  # д. 10
            r'дом\s+(\d+)',  # дом 10
            r'кв\.\s*(\d+)',  # кв. 25
            r'квартира\s+(\d+)'  # квартира 25
        ]

        # Способы доставки
        self.delivery_methods = {
            "courier": ["курьер", "курьером", "доставка курьером"],
            "pickup": ["самовывоз", "забрать", "pickup", "пункт выдачи"],
            "post": ["почта", "почтой", "российская почта"],
            "express": ["экспресс", "быстрая доставка", "срочно"]
        }

    async def enter(self, context: StateContext) -> StateResult:
        """Вход в состояние обработки доставки."""
        self.logger.info("Вход в состояние обработки доставки")

        greeting = "Помогу с вопросами доставки! Что вас интересует?"

        return StateResult(
            response=greeting,
            requires_input=True,
            suggested_actions=[
                "Способы доставки",
                "Изменить адрес",
                "Отследить посылку",
                "Время доставки"
            ]
        )

    async def handle_input(self, context: StateContext, message: str,
                          intent: str | None = None,
                          entities: dict[str, Any] | None = None) -> StateResult:
        """Обработка пользовательского ввода в состоянии доставки."""
        if not self.validate_input(message, intent):
            return StateResult(
                response="Не поняла ваш вопрос по доставке. Уточните, пожалуйста.",
                requires_input=True
            )

        message_lower = message.lower().strip()

        # Извлекаем адрес, если есть
        address_parts = self._extract_address(message)
        if address_parts:
            context.add_entity("address_parts", address_parts)

        # Определяем способ доставки
        delivery_method = self._detect_delivery_method(message_lower)
        if delivery_method:
            context.add_entity("delivery_method", delivery_method)

        # Обработка различных намерений
        if intent == "delivery_methods" or any(word in message_lower for word in ["способы", "как доставить", "варианты доставки"]):
            return await self._handle_delivery_methods(context)

        elif intent == "change_address" or any(word in message_lower for word in ["изменить адрес", "новый адрес", "другой адрес"]):
            return await self._handle_change_address(context, message)

        elif intent == "track_delivery" or any(word in message_lower for word in ["отследить", "где посылка", "статус доставки"]):
            return await self._handle_track_delivery(context, message)

        elif intent == "delivery_time" or any(word in message_lower for word in ["время доставки", "когда привезут", "сроки"]):
            return await self._handle_delivery_time(context, message)

        elif intent == "delivery_cost" or any(word in message_lower for word in ["стоимость", "цена доставки", "сколько стоит"]):
            return await self._handle_delivery_cost(context, message)

        elif any(word in message_lower for word in ["заказ", "товар", "оплата"]):
            return StateResult(
                response="Для вопросов по заказам и оплате перехожу к соответствующему специалисту.",
                next_state="order",
                should_continue=True
            )

        else:
            return await self._handle_general_delivery_question(context, message)

    async def _handle_delivery_methods(self, context: StateContext) -> StateResult:
        """Обработка запроса о способах доставки."""
        methods_info = """
Доступные способы доставки:

🚚 Курьерская доставка
• По Москве: 300 руб., 1-2 дня
• По МО: 400 руб., 2-3 дня
• По России: от 500 руб., 3-7 дней

📦 Пункты выдачи
• Бесплатно от 1000 руб.
• Более 2000 пунктов
• Удобное время получения

📮 Почта России
• От 200 руб.
• 7-14 дней
• До отделения связи

⚡ Экспресс-доставка
• В день заказа: +500 руб.
• Только по Москве
        """.strip()

        return StateResult(
            response=methods_info,
            requires_input=True,
            suggested_actions=[
                "Выбрать курьерскую доставку",
                "Найти пункт выдачи",
                "Экспресс-доставка",
                "Рассчитать стоимость"
            ]
        )

    async def _handle_change_address(self, context: StateContext, message: str) -> StateResult:
        """Обработка изменения адреса доставки."""
        address_parts = context.get_entity("address_parts")
        order_number = context.get_entity("order_number")

        if address_parts:
            address_text = self._format_address(address_parts)
            response = f"Понял, новый адрес: {address_text}."

            if order_number:
                response += f"\n\nИзменяю адрес доставки для заказа №{order_number}."
            else:
                response += "\n\nДля какого заказа изменить адрес? Укажите номер заказа."

        else:
            response = """
Для изменения адреса доставки укажите:
• Город
• Улица и номер дома
• Квартира (если нужно)
• Номер заказа

Например: "г. Москва, ул. Ленина, д. 10, кв. 25, заказ 123456"
            """.strip()

        return StateResult(
            response=response,
            requires_input=True,
            suggested_actions=[
                "Подтвердить изменение",
                "Указать номер заказа",
                "Выбрать из сохраненных адресов"
            ]
        )

    async def _handle_track_delivery(self, context: StateContext, message: str) -> StateResult:
        """Обработка отслеживания доставки."""
        order_number = context.get_entity("order_number") or self._extract_order_number(message)

        if order_number:
            # TODO: Интеграция с реальной системой отслеживания
            mock_tracking_info = {
                "status": "В пути",
                "current_location": "Сортировочный центр г. Москва",
                "estimated_delivery": "Завтра, 15:00-18:00",
                "courier_phone": "+7 (999) 123-45-67"
            }

            response = f"""
Отслеживание заказа №{order_number}:

📍 Статус: {mock_tracking_info['status']}
🚚 Местоположение: {mock_tracking_info['current_location']}
⏰ Ожидаемая доставка: {mock_tracking_info['estimated_delivery']}
📞 Телефон курьера: {mock_tracking_info['courier_phone']}

Курьер свяжется с вами за час до доставки.
            """.strip()

        else:
            response = "Для отслеживания доставки укажите номер заказа или трек-номер."

        return StateResult(
            response=response,
            requires_input=True,
            suggested_actions=[
                "Связаться с курьером",
                "Изменить время доставки",
                "Другой заказ"
            ]
        )

    async def _handle_delivery_time(self, context: StateContext, message: str) -> StateResult:
        """Обработка вопросов о времени доставки."""
        delivery_method = context.get_entity("delivery_method")

        if delivery_method == "courier":
            response = """
Время курьерской доставки:
🕐 По Москве: 1-2 рабочих дня
🕐 По МО: 2-3 рабочих дня
🕐 По России: 3-7 рабочих дней

Доставка с 9:00 до 21:00
Можно выбрать удобный интервал.
            """.strip()

        elif delivery_method == "express":
            response = """
Экспресс-доставка:
⚡ В день заказа до 23:00
⚡ Только по Москве в пределах МКАД
⚡ Заказ должен быть оформлен до 15:00
            """.strip()

        else:
            response = """
Сроки доставки зависят от способа:

🚚 Курьер: 1-7 дней
📦 Пункт выдачи: 2-5 дней
📮 Почта: 7-14 дней
⚡ Экспресс: в день заказа

Точный срок зависит от вашего города.
            """.strip()

        return StateResult(
            response=response,
            requires_input=True,
            suggested_actions=[
                "Выбрать интервал доставки",
                "Ускорить доставку",
                "Другой способ доставки"
            ]
        )

    async def _handle_delivery_cost(self, context: StateContext, message: str) -> StateResult:
        """Обработка вопросов о стоимости доставки."""
        response = """
Стоимость доставки:

🚚 Курьерская доставка:
• Москва: 300 руб.
• МО: 400 руб.
• Регионы: от 500 руб.

📦 Пункты выдачи:
• Бесплатно от 1000 руб.
• До 1000 руб.: 150 руб.

📮 Почта России: от 200 руб.
⚡ Экспресс: +500 руб.

Точная стоимость рассчитывается при оформлении заказа.
        """.strip()

        return StateResult(
            response=response,
            requires_input=True,
            suggested_actions=[
                "Рассчитать для моего города",
                "Бесплатная доставка",
                "Способы экономии"
            ]
        )

    async def _handle_general_delivery_question(self, context: StateContext, message: str) -> StateResult:
        """Обработка общих вопросов по доставке."""
        responses = [
            "По доставке могу помочь с выбором способа, изменением адреса или отслеживанием. What интересует?",
            "Какой вопрос по доставке у вас возник?",
            "Расскажите подробнее, что нужно узнать о доставке?"
        ]

        return StateResult(
            response=random.choice(responses),
            requires_input=True,
            suggested_actions=[
                "Способы доставки",
                "Изменить адрес",
                "Отследить посылку",
                "Время доставки"
            ]
        )

    def _extract_address(self, message: str) -> dict[str, str]:
        """Извлечение компонентов адреса из сообщения."""
        address_parts = {}

        for pattern in self.address_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if 'г.' in pattern or 'город' in pattern:
                    address_parts['city'] = value
                elif 'ул.' in pattern or 'улица' in pattern:
                    address_parts['street'] = value
                elif 'д.' in pattern or 'дом' in pattern:
                    address_parts['house'] = value
                elif 'кв.' in pattern or 'квартира' in pattern:
                    address_parts['apartment'] = value

        return address_parts

    def _format_address(self, address_parts: dict[str, str]) -> str:
        """Форматирование адреса для отображения."""
        parts = []
        if 'city' in address_parts:
            parts.append(f"г. {address_parts['city']}")
        if 'street' in address_parts:
            parts.append(f"ул. {address_parts['street']}")
        if 'house' in address_parts:
            parts.append(f"д. {address_parts['house']}")
        if 'apartment' in address_parts:
            parts.append(f"кв. {address_parts['apartment']}")

        return ', '.join(parts)

    def _detect_delivery_method(self, message: str) -> str | None:
        """Определение способа доставки из сообщения."""
        for method, keywords in self.delivery_methods.items():
            if any(keyword in message for keyword in keywords):
                return method

        return None

    def _extract_order_number(self, message: str) -> str | None:
        """Извлечение номера заказа из сообщения."""
        patterns = [
            r'\b(\d{6,12})\b',  # 6-12 цифр
            r'[№#]\s*(\d+)',     # № или # с цифрами
            r'заказ\s*(\d+)',    # "заказ 123456"
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def get_available_actions(self, context: StateContext) -> list[str]:
        """Получить доступные действия в состоянии доставки."""
        base_actions = [
            "Способы доставки",
            "Время доставки",
            "Стоимость доставки"
        ]

        # Если есть номер заказа, добавляем специфичные действия
        if context.has_entity("order_number"):
            base_actions.extend([
                "Отследить доставку",
                "Изменить адрес",
                "Связаться с курьером"
            ])

        return base_actions

    def can_transition_to(self, next_state: str) -> bool:
        """Проверить возможность перехода из состояния доставки."""
        allowed_transitions = ["order", "payment", "hello", "hangup"]
        return next_state in allowed_transitions
