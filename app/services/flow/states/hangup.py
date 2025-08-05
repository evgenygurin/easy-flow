"""Состояние завершения диалога."""
import random
from typing import Any

from .base import ConversationState, StateContext, StateResult


class HangupState(ConversationState):
    """Состояние завершения диалога и эскалации к оператору."""

    def __init__(self):
        super().__init__("hangup")

        self.goodbye_messages = [
            "Спасибо за обращение! Хорошего дня!",
            "Было приятно помочь! До свидания!",
            "Обращайтесь, если возникнут вопросы. Удачи!",
            "Рада была помочь! Всего доброго!"
        ]

        self.escalation_messages = [
            "Соединяю с оператором. Ожидайте, пожалуйста...",
            "Передаю ваш вопрос живому специалисту.",
            "Оператор скоро с вами свяжется. Оставайтесь на связи.",
            "Переключаю на человека-консультанта."
        ]

    async def enter(self, context: StateContext) -> StateResult:
        """Вход в состояние завершения диалога."""
        self.logger.info("Вход в состояние завершения диалога")

        # Проверяем причину завершения
        escalation_reason = context.get_session_data("escalation_reason")
        requires_human = context.should_escalate()

        if escalation_reason or requires_human:
            return await self._handle_escalation(context, escalation_reason)
        else:
            return await self._handle_normal_goodbye(context)

    async def handle_input(self, context: StateContext, message: str,
                          intent: str | None = None,
                          entities: dict[str, Any] | None = None) -> StateResult:
        """Обработка пользовательского ввода в состоянии завершения."""
        if not self.validate_input(message, intent):
            return StateResult(
                response="До свидания!",
                should_continue=False,
                requires_input=False
            )

        message_lower = message.lower().strip()

        # Если пользователь хочет продолжить
        if any(word in message_lower for word in ["не", "подожди", "еще вопрос", "постой"]):
            return StateResult(
                response="Хорошо, я остаюсь на связи! Какой у вас вопрос?",
                next_state="hello",
                should_continue=True
            )

        # Если пользователь хочет оператора
        elif any(word in message_lower for word in ["оператор", "человек", "менеджер", "специалист"]):
            return await self._handle_escalation(context, "user_request")

        # Благодарность
        elif any(word in message_lower for word in ["спасибо", "благодарю", "thanks"]):
            return StateResult(
                response="Пожалуйста! Рада была помочь. До свидания!",
                should_continue=False,
                requires_input=False
            )

        # Жалобы или проблемы
        elif any(word in message_lower for word in ["жалоба", "проблема", "не помогли", "плохо"]):
            return await self._handle_escalation(context, "complaint")

        # Обычное завершение
        else:
            return await self._handle_normal_goodbye(context)

    async def _handle_normal_goodbye(self, context: StateContext) -> StateResult:
        """Обработка обычного завершения диалога."""
        goodbye_message = random.choice(self.goodbye_messages)

        # Добавляем персонализацию, если есть данные
        user_name = context.get_user_preference("name")
        if user_name:
            goodbye_message = f"{user_name}, {goodbye_message.lower()}"

        # Добавляем краткую сводку, если диалог был длинным
        if len(context.conversation_history) > 6:
            summary = self._generate_conversation_summary(context)
            if summary:
                goodbye_message = f"{summary}\n\n{goodbye_message}"

        return StateResult(
            response=goodbye_message,
            should_continue=False,
            requires_input=False,
            metadata={
                "conversation_completed": True,
                "satisfaction_survey": True
            }
        )

    async def _handle_escalation(self, context: StateContext, reason: str | None) -> StateResult:
        """Обработка эскалации к оператору."""
        escalation_message = random.choice(self.escalation_messages)

        # Персонализируем сообщение в зависимости от причины
        if reason == "complaint":
            escalation_message = "Понимаю ваше недовольство. Соединяю с менеджером для решения вопроса."
        elif reason == "complex_issue":
            escalation_message = "Этот вопрос требует специальных знаний. Передаю эксперту."
        elif reason == "technical_issue":
            escalation_message = "Соединяю с техническим специалистом."

        # Добавляем информацию о времени ожидания
        wait_info = self._get_wait_time_info()
        full_message = f"{escalation_message}\n\n{wait_info}"

        # Сохраняем контекст для оператора
        operator_context = self._prepare_operator_context(context, reason)

        return StateResult(
            response=full_message,
            should_continue=False,
            requires_input=False,
            metadata={
                "escalated_to_human": True,
                "escalation_reason": reason,
                "operator_context": operator_context,
                "priority": self._determine_priority(reason, context)
            }
        )

    def _generate_conversation_summary(self, context: StateContext) -> str | None:
        """Генерация краткой сводки диалога."""
        if not context.conversation_history:
            return None

        # Собираем ключевые моменты
        key_points = []

        # Основные интенты
        if context.current_intent:
            intent_descriptions = {
                "order_inquiry": "обсуждали заказ",
                "payment_inquiry": "разбирали вопросы оплаты",
                "shipping_inquiry": "говорили о доставке",
                "complaint": "рассматривали жалобу",
                "product_info": "изучали информацию о товаре"
            }

            if context.current_intent in intent_descriptions:
                key_points.append(intent_descriptions[context.current_intent])

        # Извлеченные сущности
        if context.has_entity("order_number"):
            order_num = context.get_entity("order_number")
            key_points.append(f"работали с заказом №{order_num}")

        if key_points:
            return f"Сегодня мы {', '.join(key_points)}."

        return None

    def _get_wait_time_info(self) -> str:
        """Получение информации о времени ожидания оператора."""
        # TODO: Реальная интеграция с системой управления очередями

        import datetime

        current_hour = datetime.datetime.now().hour

        if 9 <= current_hour <= 18:  # Рабочие часы
            return "⏱️ Среднее время ожидания: 3-5 минут\n📞 Оператор скоро с вами свяжется"
        elif 18 < current_hour <= 22:  # Вечерние часы
            return "⏱️ Среднее время ожидания: 5-10 минут\n📞 Работаем до 22:00"
        else:  # Ночные часы
            return "🌙 Операторы недоступны с 22:00 до 9:00\n📧 Можете оставить сообщение - ответим утром"

    def _prepare_operator_context(self, context: StateContext, reason: str | None) -> dict[str, Any]:
        """Подготовка контекста для передачи оператору."""
        operator_context = {
            "user_id": context.user_id,
            "session_id": context.session_id,
            "platform": context.platform.value,
            "escalation_reason": reason,
            "conversation_length": len(context.conversation_history),
            "last_intent": context.current_intent,
            "extracted_entities": context.extracted_entities.copy(),
            "user_preferences": context.user_data.copy(),
            "state_history": context.state_history.copy()
        }

        # Добавляем последние сообщения для контекста
        recent_messages = context.conversation_history[-6:] if len(context.conversation_history) > 6 else context.conversation_history
        operator_context["recent_messages"] = [
            {
                "content": msg.content,
                "type": msg.message_type.value,
                "timestamp": msg.created_at.isoformat()
            }
            for msg in recent_messages
        ]

        return operator_context

    def _determine_priority(self, reason: str | None, context: StateContext) -> str:
        """Определение приоритета тикета для оператора."""
        high_priority_reasons = ["complaint", "billing_dispute", "technical_issue"]
        high_priority_keywords = ["срочно", "urgent", "critical", "не работает"]

        if reason in high_priority_reasons:
            return "high"

        # Проверяем последние сообщения на наличие срочных слов
        recent_messages = context.conversation_history[-3:]
        for msg in recent_messages:
            if any(keyword in msg.content.lower() for keyword in high_priority_keywords):
                return "high"

        # Длинная конversация может означать сложную проблему
        if len(context.conversation_history) > 12:
            return "medium"

        return "normal"

    def get_available_actions(self, context: StateContext) -> list[str]:
        """Получить доступные действия в состоянии завершения."""
        escalation_reason = context.get_session_data("escalation_reason")

        if escalation_reason:
            return [
                "Ожидать оператора",
                "Оставить сообщение",
                "Перезвонить позже"
            ]
        else:
            return [
                "Завершить диалог",
                "Задать еще вопрос",
                "Оценить общение"
            ]

    def can_transition_to(self, next_state: str) -> bool:
        """Проверить возможность перехода из состояния завершения."""
        # Из состояния завершения можно только вернуться к началу
        allowed_transitions = ["hello"]
        return next_state in allowed_transitions
