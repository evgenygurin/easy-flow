"""Состояние обработки платежей."""
import random
import re
from typing import Any

from .base import ConversationState, StateContext, StateResult


class PaymentState(ConversationState):
    """Состояние для работы с платежами - выбор способа, оплата, возвраты."""

    def __init__(self):
        super().__init__("payment")

        # Доступные способы оплаты
        self.payment_methods = {
            "card": ["карта", "картой", "банковская карта", "visa", "mastercard"],
            "cash": ["наличные", "наличными", "деньги", "кэш"],
            "online": ["онлайн", "интернет", "сбербанк онлайн", "тинькофф"],
            "yoomoney": ["яндекс деньги", "yoomoney", "яндекс.деньги"],
            "qr": ["qr", "кью ар", "qr код", "по коду"]
        }

        # Паттерны для сумм
        self.amount_patterns = [
            r'(\d+)\s*руб',
            r'(\d+)\s*₽',
            r'(\d+)\s*рублей',
            r'(\d+)\s*тысяч',
            r'(\d+\.?\d*)\s*тыс'
        ]

    async def enter(self, context: StateContext) -> StateResult:
        """Вход в состояние обработки платежей."""
        self.logger.info("Вход в состояние обработки платежей")

        greeting = "Помогу с оплатой! Какой вопрос по платежам у вас возник?"

        return StateResult(
            response=greeting,
            requires_input=True,
            suggested_actions=[
                "Способы оплаты",
                "Оплатить заказ",
                "Проблемы с оплатой",
                "Вернуть деньги"
            ]
        )

    async def handle_input(self, context: StateContext, message: str,
                          intent: str | None = None,
                          entities: dict[str, Any] | None = None) -> StateResult:
        """Обработка пользовательского ввода в состоянии платежей."""
        if not self.validate_input(message, intent):
            return StateResult(
                response="Не поняла ваш вопрос по оплате. Уточните, пожалуйста.",
                requires_input=True
            )

        message_lower = message.lower().strip()

        # Извлекаем сумму, если есть
        amount = self._extract_amount(message)
        if amount:
            context.add_entity("payment_amount", amount)

        # Определяем способ оплаты
        payment_method = self._detect_payment_method(message_lower)
        if payment_method:
            context.add_entity("payment_method", payment_method)

        # Обработка различных намерений
        if intent == "payment_methods" or any(word in message_lower for word in ["способы", "как оплатить", "варианты оплаты"]):
            return await self._handle_payment_methods(context)

        elif intent == "make_payment" or any(word in message_lower for word in ["оплатить", "заплатить", "перевести"]):
            return await self._handle_make_payment(context, message)

        elif intent == "payment_problem" or any(word in message_lower for word in ["не прошла", "ошибка", "проблема", "не получается"]):
            return await self._handle_payment_problem(context, message)

        elif intent == "refund" or any(word in message_lower for word in ["вернуть", "возврат", "отменить платеж"]):
            return await self._handle_refund_request(context, message)

        elif intent == "check_payment" or any(word in message_lower for word in ["проверить", "статус", "прошла ли"]):
            return await self._handle_check_payment(context, message)

        elif any(word in message_lower for word in ["заказ", "товар", "купить"]):
            return StateResult(
                response="Для оплаты заказа нужно сначала его оформить. Перехожу к заказам.",
                next_state="order",
                should_continue=True
            )

        else:
            return await self._handle_general_payment_question(context, message)

    async def _handle_payment_methods(self, context: StateContext) -> StateResult:
        """Обработка запроса о способах оплаты."""
        methods_info = """
Доступные способы оплаты:

💳 Банковская карта (Visa, MasterCard, МИР)
💰 Наличные курьеру или в магазине
🌐 Онлайн-банкинг (Сбербанк Онлайн, Тинькофф)
🔗 YooMoney (Яндекс.Деньги)
📱 QR-код через банковское приложение

Все платежи защищены SSL-шифрованием.
        """.strip()

        return StateResult(
            response=methods_info,
            requires_input=True,
            suggested_actions=[
                "Оплатить картой",
                "Оплатить онлайн",
                "Наличные курьеру",
                "QR-код"
            ]
        )

    async def _handle_make_payment(self, context: StateContext, message: str) -> StateResult:
        """Обработка запроса на оплату."""
        payment_method = context.get_entity("payment_method")
        amount = context.get_entity("payment_amount")

        if payment_method:
            method_name = self._get_method_name(payment_method)
            response = f"Отлично! Выбран способ оплаты: {method_name}."
        else:
            response = "Каким способом хотите оплатить?"

        if amount:
            response += f" Сумма к оплате: {amount} руб."

        # TODO: Интеграция с реальной платежной системой
        if payment_method == "card":
            response += "\n\nДля оплаты картой перейдите по ссылке, которую мы отправим в SMS."
        elif payment_method == "online":
            response += "\n\nВы будете перенаправлены в ваш банк для подтверждения платежа."
        elif payment_method == "qr":
            response += "\n\nПокажите QR-код в приложении вашего банка для оплаты."

        return StateResult(
            response=response,
            requires_input=True,
            suggested_actions=[
                "Подтвердить оплату",
                "Изменить способ оплаты",
                "Проблемы с оплатой"
            ]
        )

    async def _handle_payment_problem(self, context: StateContext, message: str) -> StateResult:
        """Обработка проблем с оплатой."""
        message_lower = message.lower()

        # Анализируем тип проблемы
        if any(word in message_lower for word in ["не прошла", "отклонена", "declined"]):
            problem_type = "declined"
            response = """
Платеж отклонен. Возможные причины:

• Недостаточно средств на карте
• Превышен лимит по операциям
• Карта заблокирована банком
• Технические проблемы

Рекомендации:
1. Проверьте баланс карты
2. Обратитесь в банк
3. Попробуйте другую карту
4. Используйте другой способ оплаты
            """.strip()

        elif any(word in message_lower for word in ["ошибка", "error", "не работает"]):
            problem_type = "error"
            response = """
Технические проблемы с оплатой:

1. Обновите страницу и попробуйте снова
2. Очистите кеш браузера
3. Попробуйте с другого устройства
4. Используйте другой способ оплаты

Если проблема не решается, соединю с оператором.
            """.strip()

        else:
            problem_type = "general"
            response = "Опишите подробнее, какая проблема возникла с оплатой?"

        context.add_entity("payment_problem_type", problem_type)

        return StateResult(
            response=response,
            requires_input=True,
            suggested_actions=[
                "Попробовать еще раз",
                "Другой способ оплаты",
                "Связаться с банком",
                "Связаться с оператором"
            ]
        )

    async def _handle_refund_request(self, context: StateContext, message: str) -> StateResult:
        """Обработка запроса на возврат средств."""
        order_number = context.get_entity("order_number")

        if not order_number:
            response = "Для возврата средств укажите номер заказа или платежа."
        else:
            # TODO: Интеграция с системой возвратов
            response = f"""
Возврат средств по заказу №{order_number}:

⏰ Сроки возврата:
• На карту: 3-5 рабочих дней
• Электронные кошельки: 1-3 рабочих дня
• Наличные: при возврате товара

📋 Необходимые документы:
• Чек или подтверждение оплаты
• Паспорт (для крупных сумм)

Подтверждаете запрос на возврат?
            """.strip()

        return StateResult(
            response=response,
            requires_input=True,
            suggested_actions=[
                "Подтвердить возврат",
                "Указать номер заказа",
                "Условия возврата",
                "Связаться с оператором"
            ]
        )

    async def _handle_check_payment(self, context: StateContext, message: str) -> StateResult:
        """Обработка проверки статуса платежа."""
        # TODO: Интеграция с реальной платежной системой

        mock_payment_status = {
            "status": "Успешно",
            "amount": "2500 руб.",
            "method": "Банковская карта *1234",
            "date": "15.03.2024 14:30"
        }

        response = f"""
Статус платежа:
✅ {mock_payment_status['status']}
💰 Сумма: {mock_payment_status['amount']}
💳 Способ: {mock_payment_status['method']}
📅 Дата: {mock_payment_status['date']}

Нужна справка об оплате?
        """.strip()

        return StateResult(
            response=response,
            requires_input=True,
            suggested_actions=[
                "Справка об оплате",
                "Чек на email",
                "Другой платеж",
                "Готово"
            ]
        )

    async def _handle_general_payment_question(self, context: StateContext, message: str) -> StateResult:
        """Обработка общих вопросов по платежам."""
        responses = [
            "По платежам я могу помочь с выбором способа оплаты, решением проблем или возвратом средств. Что интересует?",
            "Какой вопрос по оплате у вас возник?",
            "Расскажите подробнее, что нужно сделать с платежом?"
        ]

        return StateResult(
            response=random.choice(responses),
            requires_input=True,
            suggested_actions=[
                "Способы оплаты",
                "Оплатить заказ",
                "Проблемы с оплатой",
                "Вернуть деньги"
            ]
        )

    def _extract_amount(self, message: str) -> str | None:
        """Извлечение суммы из сообщения."""
        for pattern in self.amount_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _detect_payment_method(self, message: str) -> str | None:
        """Определение способа оплаты из сообщения."""
        for method, keywords in self.payment_methods.items():
            if any(keyword in message for keyword in keywords):
                return method

        return None

    def _get_method_name(self, method: str) -> str:
        """Получить читаемое название способа оплаты."""
        method_names = {
            "card": "Банковская карта",
            "cash": "Наличные",
            "online": "Онлайн-банкинг",
            "yoomoney": "YooMoney",
            "qr": "QR-код"
        }

        return method_names.get(method, method)

    def get_available_actions(self, context: StateContext) -> list[str]:
        """Получить доступные действия в состоянии платежей."""
        base_actions = [
            "Способы оплаты",
            "Оплатить заказ",
            "Проверить платеж"
        ]

        # Если есть проблема с платежом, добавляем специфичные действия
        if context.has_entity("payment_problem_type"):
            base_actions.extend([
                "Решить проблему",
                "Связаться с банком",
                "Другой способ оплаты"
            ])

        return base_actions

    def can_transition_to(self, next_state: str) -> bool:
        """Проверить возможность перехода из состояния платежей."""
        allowed_transitions = ["order", "shipping", "hello", "hangup"]
        return next_state in allowed_transitions
