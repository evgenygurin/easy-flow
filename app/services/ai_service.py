"""
AI сервис для генерации ответов клиентам.
"""
from typing import Optional, Dict, Any, List
import structlog
from datetime import datetime
from functools import lru_cache
import hashlib

from app.models.conversation import MessageResponse
from app.core.config import settings

logger = structlog.get_logger()


class AIResponse:
    """Ответ от AI сервиса."""
    
    def __init__(
        self,
        response: str,
        confidence: float = 0.8,
        suggested_actions: Optional[List[str]] = None,
        next_questions: Optional[List[str]] = None
    ):
        self.response = response
        self.confidence = confidence
        self.suggested_actions = suggested_actions or []
        self.next_questions = next_questions or []


class AIService:
    """Сервис для работы с AI моделями."""
    
    def __init__(self):
        # TODO: Инициализация OpenAI/YandexGPT клиентов
        self._templates = self._load_response_templates()
        self._knowledge_base = self._load_knowledge_base()
    
    async def generate_response(
        self,
        message: str,
        intent: Optional[str] = None,
        entities: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[MessageResponse]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> AIResponse:
        """
        Генерация ответа на сообщение клиента.
        
        Args:
            message: Сообщение пользователя
            intent: Распознанное намерение
            entities: Извлеченные сущности
            conversation_history: История диалога
            user_context: Контекст пользователя
            
        Returns:
            AIResponse: Ответ от AI
        """
        try:
            logger.info(
                "Генерация ответа AI",
                intent=intent,
                entities_count=len(entities) if entities else 0,
                history_length=len(conversation_history) if conversation_history else 0
            )
            
            # Если есть готовый шаблон для намерения, используем его
            if intent and intent in self._templates:
                response = self._generate_template_response(intent, entities)
                return AIResponse(
                    response=response,
                    confidence=0.9,
                    suggested_actions=self._get_suggested_actions(intent),
                    next_questions=self._get_next_questions(intent)
                )
            
            # Если есть информация в базе знаний
            kb_response = self._search_knowledge_base(message, intent)
            if kb_response:
                return AIResponse(
                    response=kb_response,
                    confidence=0.8,
                    suggested_actions=self._get_suggested_actions(intent)
                )
            
            # Генерация ответа через LLM (заглушка)
            llm_response = await self._generate_llm_response(
                message, intent, entities, conversation_history, user_context
            )
            
            return llm_response
            
        except Exception as e:
            logger.error("Ошибка генерации ответа AI", error=str(e))
            # Fallback ответ
            return AIResponse(
                response="Извините, я не совсем понял ваш вопрос. Можете переформулировать?",
                confidence=0.3
            )
    
    def _generate_template_response(
        self, 
        intent: str, 
        entities: Optional[Dict[str, Any]] = None
    ) -> str:
        """Генерация ответа на основе шаблона."""
        template = self._templates.get(intent, {}).get("response", "")
        
        if not template:
            return "Извините, я не могу помочь с этим вопросом."
        
        # Подстановка сущностей в шаблон
        if entities:
            try:
                response = template.format(**entities)
            except KeyError:
                # Если не все сущности найдены, используем шаблон как есть
                response = template
        else:
            response = template
        
        return response
    
    @lru_cache(maxsize=128)
    def _generate_template_response_cached(
        self, 
        intent: str, 
        entities_hash: str
    ) -> str:
        """Кэшированная версия генерации ответа на основе шаблона."""
        # Восстанавливаем entities из хэша (упрощенная реализация)
        # В реальной реализации можно использовать более сложную систему кэширования
        return self._generate_template_response(intent, None)
    
    def _search_knowledge_base(self, message: str, intent: Optional[str]) -> Optional[str]:
        """Поиск ответа в базе знаний."""
        message_lower = message.lower()
        
        # Простой поиск по ключевым словам
        for kb_item in self._knowledge_base:
            for keyword in kb_item["keywords"]:
                if keyword in message_lower:
                    return kb_item["response"]
        
        return None
    
    @lru_cache(maxsize=256)
    def _search_knowledge_base_cached(self, message: str, intent: Optional[str]) -> Optional[str]:
        """Кэшированная версия поиска в базе знаний."""
        return self._search_knowledge_base(message, intent)
    
    async def _generate_llm_response(
        self,
        message: str,
        intent: Optional[str],
        entities: Optional[Dict[str, Any]],
        conversation_history: Optional[List[MessageResponse]],
        user_context: Optional[Dict[str, Any]]
    ) -> AIResponse:
        """Генерация ответа через LLM (OpenAI/YandexGPT)."""
        
        # Формируем промпт для LLM
        system_prompt = self._build_system_prompt(intent)
        user_prompt = self._build_user_prompt(message, entities, conversation_history)
        
        # TODO: Здесь будет реальный вызов OpenAI/YandexGPT API
        # Пока возвращаем заглушку
        
        response_text = self._generate_fallback_response(intent, message)
        
        return AIResponse(
            response=response_text,
            confidence=0.7,
            suggested_actions=self._get_suggested_actions(intent)
        )
    
    def _build_system_prompt(self, intent: Optional[str]) -> str:
        """Построение системного промпта."""
        base_prompt = """
        Ты - AI помощник для службы поддержки клиентов e-commerce платформы.
        Твоя задача - помочь клиентам с их вопросами и проблемами.
        
        Правила:
        1. Отвечай на русском языке
        2. Будь вежливым и профессиональным
        3. Давай конкретные и полезные ответы
        4. Если не знаешь ответа, честно скажи об этом
        5. Предлагай следующие шаги для решения проблемы
        """
        
        if intent:
            intent_specific = {
                "order_status": "Клиент интересуется статусом заказа. Запроси номер заказа если его нет.",
                "complaint": "Клиент подает жалобу. Будь особенно внимательным и сочувствующим.",
                "refund_request": "Клиент хочет вернуть товар. Объясни процедуру возврата.",
                "product_info": "Клиент спрашивает о товаре. Предоставь подробную информацию.",
            }
            
            if intent in intent_specific:
                base_prompt += f"\n\nТекущая ситуация: {intent_specific[intent]}"
        
        return base_prompt
    
    def _build_user_prompt(
        self,
        message: str,
        entities: Optional[Dict[str, Any]],
        conversation_history: Optional[List[MessageResponse]]
    ) -> str:
        """Построение пользовательского промпта."""
        prompt = f"Сообщение клиента: {message}"
        
        if entities:
            prompt += f"\nИзвлеченная информация: {entities}"
        
        if conversation_history and len(conversation_history) > 1:
            prompt += "\n\nПредыдущий контекст диалога:"
            for msg in conversation_history[-5:]:  # Последние 5 сообщений
                prompt += f"\n{msg.message_type}: {msg.content}"
        
        return prompt
    
    def _generate_fallback_response(self, intent: Optional[str], message: str) -> str:
        """Генерация fallback ответа."""
        fallback_responses = {
            "greeting": "Здравствуйте! Как я могу вам помочь?",
            "order_status": "Для проверки статуса заказа мне нужен номер заказа. Можете его предоставить?",
            "product_info": "Я готов предоставить информацию о товаре. Уточните, пожалуйста, о каком товаре идет речь?",
            "complaint": "Понимаю ваше беспокойство. Расскажите подробнее о проблеме, и я постараюсь помочь.",
            "refund_request": "Для оформления возврата нужна дополнительная информация. Укажите номер заказа и причину возврата.",
            "technical_support": "Опишите подробнее техническую проблему, с которой вы столкнулись.",
            "goodbye": "Спасибо за обращение! Если у вас возникнут еще вопросы, обращайтесь."
        }
        
        return fallback_responses.get(
            intent, 
            "Я готов помочь вам. Не могли бы вы уточнить ваш вопрос?"
        )
    
    def _get_suggested_actions(self, intent: Optional[str]) -> List[str]:
        """Получение предлагаемых действий."""
        actions = {
            "order_status": [
                "Проверить статус заказа",
                "Связаться с курьером",
                "Изменить адрес доставки"
            ],
            "product_info": [
                "Посмотреть характеристики",
                "Прочитать отзывы",
                "Сравнить с похожими товарами"
            ],
            "refund_request": [
                "Оформить возврат",
                "Узнать статус возврата",
                "Связаться с оператором"
            ],
            "complaint": [
                "Подать официальную жалобу",
                "Связаться с менеджером",
                "Получить компенсацию"
            ]
        }
        
        return actions.get(intent, [])
    
    def _get_next_questions(self, intent: Optional[str]) -> List[str]:
        """Получение следующих вопросов."""
        questions = {
            "order_status": [
                "Когда был сделан заказ?",
                "Какой способ доставки был выбран?",
                "Нужно ли изменить контактные данные?"
            ],
            "product_info": [
                "Интересуют ли вас похожие товары?",
                "Нужна ли помощь с выбором?",
                "Хотите узнать о скидках?"
            ]
        }
        
        return questions.get(intent, [])
    
    def _load_response_templates(self) -> Dict[str, Dict[str, Any]]:
        """Загрузка шаблонов ответов."""
        return {
            "greeting": {
                "response": "Здравствуйте! Меня зовут AI-помощник, и я готов помочь вам с любыми вопросами по заказам и товарам. Что вас интересует?"
            },
            "order_status": {
                "response": "Проверяю статус заказа №{order_number}... Ваш заказ находится в обработке. Ожидаемая дата доставки: завтра."
            },
            "goodbye": {
                "response": "Спасибо за обращение! Хорошего дня и удачных покупок! Если у вас возникнут еще вопросы, я всегда готов помочь."
            }
        }
    
    def _load_knowledge_base(self) -> List[Dict[str, Any]]:
        """Загрузка базы знаний."""
        return [
            {
                "keywords": ["время доставки", "сколько доставляют", "когда привезут"],
                "response": "Обычно доставка занимает 1-3 рабочих дня в пределах города и 3-7 дней в другие регионы."
            },
            {
                "keywords": ["способы оплаты", "как оплатить", "карта"],
                "response": "Мы принимаем оплату банковскими картами, через SberPay, YooMoney, а также наличными при получении."
            },
            {
                "keywords": ["возврат", "как вернуть", "не подошел"],
                "response": "Вы можете вернуть товар в течение 14 дней с момента получения. Товар должен быть в оригинальной упаковке."
            },
            {
                "keywords": ["гарантия", "сломался", "не работает"],
                "response": "На все товары действует гарантия производителя. При поломке обратитесь к нам с фотографиями и описанием проблемы."
            }
        ]