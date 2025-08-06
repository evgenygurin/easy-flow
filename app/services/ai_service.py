"""AI сервис для генерации ответов клиентам."""
import os
from functools import lru_cache
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.conversation import MessageResponse
from app.services.cache_service import cache_service
from app.services.embeddings_service import embeddings_service


logger = structlog.get_logger()


class AIResponse(BaseModel):
    """Ответ от AI сервиса."""

    response: str = Field(..., description="Ответ AI системы")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Уверенность в ответе")
    suggested_actions: list[str] = Field(default_factory=list, description="Предлагаемые действия")
    next_questions: list[str] = Field(default_factory=list, description="Следующие вопросы")


class AIService:
    """Сервис для работы с AI моделями."""

    def __init__(self) -> None:
        # Проверяем, запущены ли тесты
        if os.environ.get("TESTING") == "1":
            self._openai_client = None
            self._yandex_gpt_available = False
            logger.info("Режим тестирования: OpenAI клиент не инициализирован")
        else:
            # Инициализация OpenAI клиента
            from openai import AsyncOpenAI
            if settings.OPENAI_API_KEY:
                self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            else:
                self._openai_client = None
                logger.warning("OpenAI API ключ не настроен")

            # TODO: Инициализация YandexGPT клиента
            self._yandex_gpt_available = bool(settings.YANDEX_GPT_API_KEY)

        # Загрузка шаблонов и базы знаний

        self._templates: dict[str, dict[str, Any]] = self._load_response_templates()
        self._knowledge_base: list[dict[str, Any]] = self._load_knowledge_base()

        # Инициализация embeddings индекса базы знаний
        self._knowledge_embeddings: dict[str, Any] = {}
        self._knowledge_items: dict[str, dict[str, Any]] = {}
        self._initialize_knowledge_base_embeddings()

    async def generate_response(
        self,
        message: str,
        intent: str | None = None,
        entities: dict[str, Any] | None = None,
        conversation_history: list[MessageResponse] | None = None,
        user_context: dict[str, Any] | None = None
    ) -> AIResponse:
        """Генерация ответа на сообщение клиента.

        Args:
        ----
            message: Сообщение пользователя
            intent: Распознанное намерение
            entities: Извлеченные сущности
            conversation_history: История диалога
            user_context: Контекст пользователя

        Returns:
        -------
            AIResponse: Ответ от AI

        """
        try:
            logger.info(
                "Генерация ответа AI",
                intent=intent,
                entities_count=len(entities) if entities else 0,
                history_length=len(conversation_history) if conversation_history else 0
            )

            # Проверяем кэш на наличие готового ответа
            cached_response = await cache_service.get_ai_response_cache(message, intent, entities)
            if cached_response:
                logger.info("Использован кэшированный AI ответ")
                return AIResponse(**cached_response)

            # Если есть готовый шаблон для намерения, используем его
            if intent and intent in self._templates:
                response = self._generate_template_response(intent, entities)
                ai_response = AIResponse(
                    response=response,
                    confidence=0.9,
                    suggested_actions=self._get_suggested_actions(intent),
                    next_questions=self._get_next_questions(intent)
                )

                # Кэшируем шаблонный ответ на 2 часа
                await cache_service.set_ai_response_cache(
                    message, intent, entities, ai_response.model_dump(), ttl_seconds=7200
                )

                return ai_response

            # Если есть информация в базе знаний (сначала пробуем embeddings поиск)
            kb_response = await self._search_knowledge_base_embeddings(message, intent)
            if not kb_response:
                # Fallback на старый метод поиска по ключевым словам
                kb_response = self._search_knowledge_base(message, intent)

            if kb_response:
                ai_response = AIResponse(
                    response=kb_response,
                    confidence=0.8,
                    suggested_actions=self._get_suggested_actions(intent)
                )

                # Кэшируем ответ из базы знаний на 4 часа
                await cache_service.set_ai_response_cache(
                    message, intent, entities, ai_response.model_dump(), ttl_seconds=14400
                )

                return ai_response

            # Генерация ответа через LLM
            llm_response = await self._generate_llm_response(
                message, intent, entities, conversation_history, user_context
            )

            # Кэшируем LLM ответ на 1 час
            await cache_service.set_ai_response_cache(
                message, intent, entities, llm_response.model_dump(), ttl_seconds=3600
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
        entities: dict[str, Any] | None = None
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

    def _search_knowledge_base(self, message: str, intent: str | None) -> str | None:
        """Поиск ответа в базе знаний."""
        message_lower = message.lower()

        # Простой поиск по ключевым словам
        for kb_item in self._knowledge_base:
            for keyword in kb_item["keywords"]:
                if keyword in message_lower:
                    return kb_item["response"]

        return None

    @lru_cache(maxsize=256)
    def _search_knowledge_base_cached(self, message: str, intent: str | None) -> str | None:
        """Кэшированная версия поиска в базе знаний."""
        return self._search_knowledge_base(message, intent)

    async def _generate_llm_response(
        self,
        message: str,
        intent: str | None,
        entities: dict[str, Any] | None,
        conversation_history: list[MessageResponse] | None,
        user_context: dict[str, Any] | None
    ) -> AIResponse:
        """Генерация ответа через LLM (OpenAI/YandexGPT)."""
        # Формируем промпт для LLM
        system_prompt = self._build_system_prompt(intent)
        user_prompt = self._build_user_prompt(message, entities, conversation_history)

        # Пробуем OpenAI GPT-4o-mini
        if self._openai_client:
            try:
                response = await self._call_openai_api(system_prompt, user_prompt, intent)
                return response
            except Exception as e:
                logger.error("Ошибка вызова OpenAI API", error=str(e))

        # Fallback на YandexGPT для русского языка
        if self._yandex_gpt_available:
            try:
                response = await self._call_yandex_gpt_api(system_prompt, user_prompt, intent)
                return response
            except Exception as e:
                logger.error("Ошибка вызова YandexGPT API", error=str(e))

        # Последний fallback на предустановленные ответы
        response_text = self._generate_fallback_response(intent, message)

        return AIResponse(
            response=response_text,
            confidence=0.7,
            suggested_actions=self._get_suggested_actions(intent)
        )

    def _build_system_prompt(self, intent: str | None) -> str:
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
        entities: dict[str, Any] | None,
        conversation_history: list[MessageResponse] | None
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

    def _generate_fallback_response(self, intent: str | None, message: str) -> str:
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
            intent or "unknown",
            "Я готов помочь вам. Не могли бы вы уточнить ваш вопрос?"
        )

    def _get_suggested_actions(self, intent: str | None) -> list[str]:
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

        return actions.get(intent or "unknown", [])

    def _get_next_questions(self, intent: str | None) -> list[str]:
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

        return questions.get(intent or "unknown", [])

    def _load_response_templates(self) -> dict[str, dict[str, Any]]:
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

    def _load_knowledge_base(self) -> list[dict[str, Any]]:
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

    async def _call_openai_api(
        self,
        system_prompt: str,
        user_prompt: str,
        intent: str | None
    ) -> AIResponse:
        """Вызов OpenAI GPT-4o-mini API."""
        try:
            # Определяем модель в зависимости от сложности запроса
            model = "gpt-4o-mini" if intent in ["greeting", "goodbye"] else "gpt-4o-mini"

            response = await self._openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=500,
                temperature=0.7,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )

            response_text = response.choices[0].message.content.strip()
            confidence = min(0.95, max(0.8, 0.9 if response.choices[0].finish_reason == "stop" else 0.8))

            return AIResponse(
                response=response_text,
                confidence=confidence,
                suggested_actions=self._get_suggested_actions(intent),
                next_questions=self._get_next_questions(intent)
            )

        except Exception as e:
            logger.error("Ошибка OpenAI API", error=str(e), intent=intent)
            raise

    async def _call_yandex_gpt_api(
        self,
        system_prompt: str,
        user_prompt: str,
        intent: str | None
    ) -> AIResponse:
        """Вызов YandexGPT API для русскоязычных запросов."""
        try:
            import aiohttp

            url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
            headers = {
                "Authorization": f"Api-Key {settings.YANDEX_GPT_API_KEY}",
                "Content-Type": "application/json"
            }

            payload = {
                "modelUri": f"gpt://{settings.YANDEX_CLOUD_FOLDER_ID}/yandexgpt-lite",
                "completionOptions": {
                    "stream": False,
                    "temperature": 0.6,
                    "maxTokens": 500
                },
                "messages": [
                    {"role": "system", "text": system_prompt},
                    {"role": "user", "text": user_prompt}
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        response_text = data["result"]["alternatives"][0]["message"]["text"]

                        return AIResponse(
                            response=response_text,
                            confidence=0.85,
                            suggested_actions=self._get_suggested_actions(intent),
                            next_questions=self._get_next_questions(intent)
                        )
                    else:
                        error_text = await response.text()
                        logger.error("YandexGPT API ошибка", status=response.status, error=error_text)
                        raise Exception(f"YandexGPT API ошибка: {response.status}")

        except Exception as e:
            logger.error("Ошибка YandexGPT API", error=str(e), intent=intent)
            raise

    def _initialize_knowledge_base_embeddings(self) -> None:
        """Асинхронная инициализация embeddings для базы знаний."""
        # В режиме тестирования пропускаем инициализацию embeddings
        if os.environ.get("TESTING") == "1":
            self._knowledge_embeddings = {"test-id": [0.1, 0.2, 0.3, 0.4, 0.5]}
            self._knowledge_items = {"test-id": {"id": "test-id", "title": "Test", "content": "Test content"}}
            logger.info("Режим тестирования: созданы тестовые данные для knowledge base")
            return

        # Запускаем инициализацию в фоне
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Если event loop уже запущен, создаем task
                asyncio.create_task(self._create_knowledge_embeddings())
            else:
                # Если event loop не запущен, запускаем синхронно
                loop.run_until_complete(self._create_knowledge_embeddings())
        except Exception as e:
            logger.warning("Не удалось инициализировать embeddings", error=str(e))

    async def _create_knowledge_embeddings(self) -> None:
        """Создать embeddings индекс для базы знаний."""
        try:
            # Преобразуем знания в формат с ID
            knowledge_with_ids = []
            for i, item in enumerate(self._knowledge_base):
                kb_item = {
                    'id': str(i),
                    'title': f"Вопрос {i+1}",
                    'content': item['response'],
                    'keywords': item['keywords']
                }
                knowledge_with_ids.append(kb_item)

            # Создаем embeddings индекс
            embeddings_dict, items_dict = await embeddings_service.create_knowledge_base_index(knowledge_with_ids)

            self._knowledge_embeddings = embeddings_dict
            self._knowledge_items = items_dict

            logger.info("Embeddings индекс базы знаний создан", items_count=len(items_dict))

        except Exception as e:
            logger.error("Ошибка создания embeddings индекса", error=str(e))

    async def _search_knowledge_base_embeddings(
        self,
        message: str,
        intent: str | None
    ) -> str | None:
        """Поиск в базе знаний с использованием embeddings."""
        if not self._knowledge_embeddings or not embeddings_service._available:
            return None

        try:
            # Поиск похожих элементов
            similar_items = await embeddings_service.search_similar_knowledge(
                query_text=message,
                knowledge_embeddings=self._knowledge_embeddings,
                knowledge_items=self._knowledge_items,
                threshold=0.6,  # Порог сходства
                top_k=1  # Берем только самый похожий
            )

            if similar_items and len(similar_items) > 0:
                best_match = similar_items[0]
                similarity_score = best_match.get('similarity_score', 0)

                logger.info(
                    "Найден ответ через embeddings поиск",
                    similarity=similarity_score,
                    content_preview=best_match['content'][:100]
                )

                return best_match['content']

            return None

        except Exception as e:
            logger.error("Ошибка embeddings поиска", error=str(e))
            return None
