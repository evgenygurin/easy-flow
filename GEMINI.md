# Gemini Code Инструкции для easy-flow

## 🤖 Архитектура AI-платформы для поддержки клиентов

Этот проект представляет собой современную AI-платформу для поддержки клиентов в e-commerce с чистой архитектурой.

### 🏗️ Clean Architecture Implementation

#### Слои архитектуры:

1. **Presentation Layer (API)**
   - `app/api/controllers/` - Контроллеры с чистой HTTP логикой
   - `app/api/routes/` - Тонкие маршруты FastAPI (максимум 10 строк)
   - `app/api/dependencies.py` - Dependency Injection

2. **Business Logic Layer**
   - `app/services/` - Все бизнес-правила и оркестрация
   - Чистые сервисы без зависимостей от HTTP или БД

3. **Data Access Layer** 
   - `app/repositories/` - Интерфейсы и реализации репозиториев
   - `app/adapters/` - Внешние интеграции (e-commerce платформы)

## 🎯 Рефакторинг Контроллеров

### До рефакторинга (Плохо):
```python
@router.post("/chat")
async def process_chat_message(request: ChatRequest):
    try:
        # ❌ Бизнес-логика в контроллере
        session_id = request.session_id or str(uuid.uuid4())
        
        # ❌ Оркестрация сервисов в контроллере
        nlp_result = await nlp_service.process_message(...)
        conversation_result = await conversation_service.process_conversation(...)
        
        # ❌ Сложное построение ответа
        return ChatResponse(...)
    except Exception as e:
        # ❌ Кастомная обработка ошибок
        raise HTTPException(...)
```

### После рефакторинга (Хорошо):
```python
@router.post("/chat")  
async def process_chat_message(
    request: ChatRequest,
    controller: ConversationController = Depends()
) -> ChatResponse:
    """Чистый маршрут - делегирует всё контроллеру"""
    return await controller.process_chat_message(request)
```

## 🛡️ Контроллеры - Только HTTP логика

### BaseController
```python
class BaseController:
    """Базовый контроллер с общими HTTP методами"""
    
    async def handle_request(self, request_func, *args, **kwargs):
        """Стандартная обработка запроса с конвертацией ошибок"""
        
    def format_response(self, data, status_code=200):
        """Стандартное форматирование ответа"""
        
    def validate_id(self, id_value: str, field_name: str = "id"):
        """Валидация ID полей"""
```

### ConversationController
```python
class ConversationController(BaseController):
    """Контроллер диалогов - ТОЛЬКО HTTP логика"""
    
    def __init__(self, conversation_service, nlp_service):
        self.conversation_service = conversation_service
        self.nlp_service = nlp_service
        
    async def process_chat_message(self, request):
        """ТОЛЬКО валидация входа и делегирование сервису"""
        validated_request = self._validate_chat_request(request)
        return await self.handle_request(
            self._process_chat_message_business_logic,
            validated_request
        )
```

## 📊 Интеграции с E-commerce

### Поддерживаемые платформы:

#### Российские платформы:
- **Wildberries** - крупнейший маркетплейс
- **Ozon** - федеральная e-commerce платформа  
- **1C-Bitrix** - CRM и e-commerce решение
- **InSales** - платформа для интернет-магазинов

#### Международные платформы:
- **Shopify** - международный лидер
- **WooCommerce** - WordPress e-commerce
- **BigCommerce** - enterprise решение
- **Magento** - гибкая платформа

### IntegrationController
```python
class IntegrationController(BaseController):
    """Контроллер интеграций с платформами"""
    
    async def sync_platform_data(self, platform_id, user_id, request):
        """Синхронизация данных с платформой"""
        # Валидация HTTP входа
        validated_platform_id = self.validate_id(platform_id)
        
        # Делегирование бизнес-логики сервису
        result = await self.handle_request(
            self.integration_service.sync_platform_data,
            validated_platform_id, user_id
        )
        
        # Форматирование HTTP ответа
        return {
            "status": "synced",
            "records_processed": result.records_processed,
            "sync_time": result.sync_time.isoformat()
        }
```

## 🔧 Сервисы - Чистая бизнес-логика

### ConversationService
```python
class ConversationService:
    """Сервис диалогов - ВСЯ бизнес-логика здесь"""
    
    async def process_conversation(
        self, user_id, session_id, message, intent, entities, platform
    ):
        """Полная обработка диалога"""
        # Генерация session_id
        # Получение/создание пользователя  
        # Сохранение сообщения
        # Обработка через AI/NLP
        # Проверка эскалации
        # Возврат результата
```

### IntegrationService  
```python
class IntegrationService:
    """Сервис интеграций с платформами"""
    
    async def sync_platform_data(self, user_id, platform_id, operation):
        """Синхронизация данных - вся логика в сервисе"""
        # Получение адаптера платформы
        # Выполнение синхронизации
        # Обработка ошибок
        # Метрики и логирование
        # Обновление БД
        return SyncResult(...)
```

## 🧩 Dependency Injection

### Чистая инъекция зависимостей:
```python
# app/api/dependencies.py

def get_conversation_controller() -> ConversationController:
    """Фабрика контроллеров с инъекцией сервисов"""
    return ConversationController(
        conversation_service=get_conversation_service(),
        nlp_service=get_nlp_service()
    )

def get_integration_controller() -> IntegrationController:
    return IntegrationController(
        integration_service=get_integration_service()
    )
```

## 🎨 Модели данных и валидация

### Pydantic модели для HTTP:
```python
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    user_id: str = Field(..., min_length=1, max_length=100)
    session_id: str | None = Field(None)
    platform: str = Field("web")
    context: dict[str, Any] | None = Field(None)

class ChatResponse(BaseModel):
    message: str
    session_id: str
    intent: str | None
    entities: dict[str, Any] | None
    confidence: float | None
    requires_human: bool = False
```

## 🚀 AI и NLP

### Conversation Flow Service:
- Управление состоянием диалогов
- Переходы между этапами разговора
- Интеграция с AI моделями (OpenAI, YandexGPT)
- Контекст пользователя и история

### NLP Service:
- Распознавание намерений (intent recognition)
- Извлечение сущностей (entity extraction)
- Анализ тональности
- Поддержка русского языка

## 📞 Поддержка каналов связи

### 📱 Мессенджеры - Полная интеграция:

#### Поддерживаемые платформы:
- **Telegram Bot API** - полная поддержка inline/reply клавиатур, медиа, стикеров
- **WhatsApp Business Cloud API** - сообщения, медиа, шаблоны, интерактивные кнопки  
- **VK Bot API** - клавиатуры, карусели, вложения, групповые чаты
- **Viber Business API** - богатые медиа, клавиатуры, широкие возможности

#### Архитектура мессенджеров:
```
MessagingController → MessagingService → PlatformAdapters
                   ↓                   ↓
            HTTP Validation      UnifiedMessage Model
                   ↓                   ↓
            Response Formatting  Platform-specific API calls
```

#### Унифицированный подход:
- **UnifiedMessage** - единая модель для всех платформ
- **Platform Adapters** - конвертация в специфичные форматы
- **Webhook Processing** - автоматическая обработка входящих сообщений
- **Rate Limiting** - соблюдение лимитов каждой платформы
- **Statistics** - метрики доставки и производительности

### 🎤 Голосовые ассистенты - Полная интеграция:

#### Реализованные платформы:
- **Yandex Alice** ✅ - российский ассистент с полным циклом обработки

#### В разработке:
- **Amazon Alexa** 🔄 - международный стандарт
- **Google Assistant** 🔄 - Google экосистема  
- **Apple Siri** 🔄 - iOS интеграция

#### Архитектура голосовых интеграций:
```
VoiceController → VoiceService → VoiceAdapters
               ↓             ↓
         HTTP Validation  VoiceMessage Model
               ↓             ↓
         Response Format   Platform-specific Processing
```

#### Unified Voice Processing:
- **VoiceMessage** - унифицированная модель голосовых сообщений
- **Voice Adapters** - конвертация в специфичные форматы платформ
- **Intent Mapping** - маппинг голосовых намерений на бизнес-действия
- **Session Management** - управление голосовыми сессиями
- **Rich Content** - поддержка карточек и интерактивного контента

## 🎤 VoiceController - Clean Architecture для голосовых ассистентов

### Принципы реализации VoiceController:

```python
class VoiceController(BaseController):
    """Контроллер голосовых ассистентов - ТОЛЬКО HTTP логика"""
    
    def __init__(self, voice_service: VoiceService):
        super().__init__()
        self.voice_service = voice_service
    
    async def process_webhook(self, request: VoiceWebhookRequest) -> VoiceWebhookResponse:
        """Обработка voice webhook - ТОЛЬКО валидация и делегирование"""
        return await self.handle_request(
            self._process_webhook_impl,
            request
        )
    
    async def _process_webhook_impl(self, request: VoiceWebhookRequest) -> VoiceWebhookResponse:
        # ✅ HTTP валидация
        validated_request = self._validate_webhook_request(request)
        
        # ✅ Конвертация platform string в enum
        platform = self._parse_voice_platform(validated_request.platform)
        
        # ✅ Делегирование в сервис
        result = await self.voice_service.process_voice_webhook(
            platform=platform,
            request_data=validated_request.payload,
            signature=validated_request.signature
        )
        
        # ✅ HTTP форматирование ответа
        return VoiceWebhookResponse(
            success=result.success,
            event_id=result.event_id,
            platform=result.platform.value,
            response=result.response
        )
```

### VoiceService - Бизнес-логика голосовых интеграций:

```python
class VoiceService:
    """Сервис голосовых ассистентов - ВСЯ бизнес-логика"""
    
    def __init__(self, integration_repository: IntegrationRepository):
        self.integration_repository = integration_repository
        self._adapters: dict[VoicePlatform, VoiceAdapter] = {}
        self._intent_mappings: dict[str, VoiceIntentMapping] = {}
    
    async def process_voice_webhook(
        self,
        platform: VoicePlatform,
        request_data: dict[str, Any],
        signature: str | None = None
    ) -> VoiceWebhookProcessingResult:
        """Обработка voice webhook - вся бизнес-логика"""
        
        # Получение адаптера платформы
        adapter = self._adapters.get(platform)
        if not adapter:
            raise ValueError(f"Voice platform {platform.value} not registered")
        
        # Обработка через адаптер
        voice_response = await adapter.process_voice_request(request_data, signature)
        
        # Форматирование для платформы
        formatted_response = await adapter.format_voice_response(voice_response)
        
        return VoiceWebhookProcessingResult(
            event_id=str(uuid.uuid4()),
            platform=platform,
            success=True,
            response=formatted_response
        )
    
    async def process_voice_message(
        self,
        platform: VoicePlatform,
        message: VoiceMessage,
        session: VoiceSession
    ) -> VoiceProcessingResult:
        """Обработка голосового сообщения через бизнес-логику"""
        
        # Маппинг голосового намерения на бизнес-действие
        business_action = None
        if message.intent:
            mapping = self._intent_mappings.get(message.intent.name)
            if mapping and message.intent.confidence >= mapping.confidence_threshold:
                business_action = mapping.business_action
        
        # Генерация ответа на основе бизнес-логики
        response = await self._generate_business_response(
            message, session, business_action
        )
        
        return VoiceProcessingResult(
            success=True,
            response=response,
            intent_confidence=message.intent.confidence if message.intent else None
        )
```

### Voice Adapters - Паттерн Адаптера для голосовых платформ:

```python
class YandexAliceAdapter(VoiceAdapter):
    """Yandex Alice специфичная реализация"""
    
    async def process_voice_request(
        self,
        request_data: dict[str, Any],
        signature: str | None = None
    ) -> VoiceResponse:
        """Обработка Alice голосового запроса"""
        
        try:
            # Верификация webhook подписи
            if self.config.verify_webhooks and signature:
                is_valid = await self.verify_request_signature(request_data, signature)
                if not is_valid:
                    raise ValueError("Invalid request signature")
            
            # Извлечение VoiceMessage из Alice формата
            voice_message = await self.extract_voice_message(request_data)
            
            # Получение/создание голосовой сессии
            session = await self._get_or_create_session(request_data)
            
            # Генерация ответа
            response = await self._generate_response(voice_message, session)
            
            return response
            
        except Exception as e:
            # Graceful error handling
            return VoiceResponse(
                text="Извините, произошла ошибка. Попробуйте ещё раз.",
                speech="Извините, произошла ошибка. Попробуйте ещё раз.",
                should_end_session=False
            )
    
    async def extract_voice_message(self, request_data: dict[str, Any]) -> VoiceMessage:
        """Конвертация Alice запроса в VoiceMessage"""
        
        request = request_data.get("request", {})
        session = request_data.get("session", {})
        
        # Извлечение намерений и сущностей из Alice NLU
        intent = None
        entities = []
        
        if "nlu" in request and "intents" in request["nlu"]:
            nlu_intents = request["nlu"]["intents"]
            if nlu_intents:
                # Берем намерение с наивысшим confidence
                intent_name, intent_data = max(
                    nlu_intents.items(),
                    key=lambda x: x[1].get("slots", {}).get("confidence", 0.0)
                )
                
                intent = VoiceIntent(
                    name=intent_name,
                    confidence=intent_data.get("slots", {}).get("confidence", 0.0),
                    entities=intent_data.get("slots", {})
                )
        
        return VoiceMessage(
            platform=VoicePlatform.YANDEX_ALICE,
            platform_message_id=request.get("request_id", ""),
            session_id=session.get("session_id", ""),
            user_id=session.get("user_id", ""),
            text=request.get("original_utterance"),
            intent=intent,
            entities=entities,
            supports_display=self._has_display_capability(request_data)
        )
    
    async def format_voice_response(self, response: VoiceResponse) -> dict[str, Any]:
        """Конвертация VoiceResponse в Alice формат"""
        
        alice_response = {
            "version": "1.0",
            "response": {
                "end_session": response.should_end_session
            }
        }
        
        # Добавление текста и речи
        if response.text:
            alice_response["response"]["text"] = response.text
        if response.speech:
            alice_response["response"]["tts"] = response.speech
        
        # Добавление Rich Card для устройств с экраном
        if response.card:
            alice_response["response"]["card"] = {
                "type": "BigImage",
                "title": response.card.title,
                "description": response.card.text or "",
                "image_id": response.card.image_url
            }
            
            # Добавление интерактивных кнопок
            if response.card.buttons:
                alice_response["response"]["buttons"] = [
                    {
                        "title": btn["title"],
                        "payload": btn.get("payload", {}),
                        "url": btn.get("url")
                    }
                    for btn in response.card.buttons[:5]  # Alice поддерживает до 5 кнопок
                ]
        
        # Добавление session state
        if response.session_attributes:
            alice_response["session_state"] = {
                "user": response.session_attributes
            }
        
        return alice_response
```

### Voice Routes - Тонкий слой:

```python
# app/api/routes/voice.py

@router.post("/webhook/{platform}", response_model=VoiceWebhookResponse)
async def process_voice_webhook(
    platform: str,
    request: Request,
    controller: VoiceController = Depends(get_voice_controller)
) -> VoiceWebhookResponse:
    """Обработка голосового webhook - делегирование контроллеру"""
    payload = await request.json()
    signature = request.headers.get("X-Hub-Signature")
    
    webhook_request = VoiceWebhookRequest(
        platform=platform,
        payload=payload,
        signature=signature
    )
    
    return await controller.process_webhook(webhook_request)

@router.post("/alice", response_model=dict[str, Any])
async def alice_webhook(
    request: Request,
    controller: VoiceController = Depends(get_voice_controller)
) -> dict[str, Any]:
    """Yandex Alice специальный endpoint"""
    payload = await request.json()
    
    webhook_request = VoiceWebhookRequest(
        platform="yandex_alice",
        payload=payload,
        signature=request.headers.get("X-Hub-Signature")
    )
    
    result = await controller.process_webhook(webhook_request)
    
    # Возврат Alice-специфичного формата
    return result.response if result.success else {
        "version": "1.0",
        "response": {
            "text": "Извините, произошла ошибка. Попробуйте позже.",
            "end_session": True
        }
    }
```

## 📱 MessagingController - Clean Architecture

### Принципы реализации MessagingController:

```python
class MessagingController(BaseController):
    """Контроллер мессенджеров - ТОЛЬКО HTTP логика"""
    
    def __init__(self, messaging_service: MessagingService):
        super().__init__()
        self.messaging_service = messaging_service
    
    async def send_message(self, request: SendMessageRequest) -> SendMessageResponse:
        """Отправка сообщения - ТОЛЬКО валидация и делегирование"""
        return await self.handle_request(
            self._send_message_impl,
            request
        )
    
    async def _send_message_impl(self, request: SendMessageRequest) -> SendMessageResponse:
        # ✅ HTTP валидация
        validated_request = self._validate_send_message_request(request)
        
        # ✅ Создание доменной модели  
        message = UnifiedMessage(
            message_id=str(uuid.uuid4()),
            platform=validated_request.platform,
            chat_id=validated_request.chat_id,
            text=validated_request.text
        )
        
        # ✅ Делегирование в сервис
        result = await self.messaging_service.send_message(
            platform=validated_request.platform,
            chat_id=validated_request.chat_id,
            message=message
        )
        
        # ✅ HTTP форматирование ответа
        return SendMessageResponse(
            success=result.success,
            message_id=result.message_id
        )
```

### MessagingService - Бизнес-логика:

```python
class MessagingService:
    """Сервис мессенджеров - ВСЯ бизнес-логика"""
    
    def __init__(self, integration_repository: IntegrationRepository):
        self.integration_repository = integration_repository
        self._adapters: dict[str, MessagingAdapter] = {}
    
    async def send_message(
        self, 
        platform: str, 
        chat_id: str, 
        message: UnifiedMessage
    ) -> DeliveryResult:
        """Отправка сообщения - вся бизнес-логика"""
        
        # Получение адаптера платформы
        adapter = self._adapters.get(platform)
        if not adapter:
            raise ValueError(f"Platform {platform} not registered")
        
        # Отправка через адаптер
        result = await adapter.send_message(chat_id, message)
        
        return result
    
    async def process_webhook(
        self,
        platform: str,
        payload: dict[str, Any]
    ) -> WebhookProcessingResult:
        """Обработка webhook - извлечение сообщений"""
        
        adapter = self._adapters.get(platform)
        if not adapter:
            raise ValueError(f"Platform {platform} not registered")
        
        # Извлечение сообщений
        messages = await adapter.receive_webhook(payload)
        
        return WebhookProcessingResult(
            event_id=str(uuid.uuid4()),
            platform=platform,
            messages=messages
        )
```

### Platform Adapters - Паттерн Адаптера:

```python
class TelegramAdapter(MessagingAdapter):
    """Telegram-специфичная реализация"""
    
    async def _send_platform_message(
        self, 
        chat_id: str, 
        message: UnifiedMessage
    ) -> DeliveryResult:
        """Конвертация и отправка через Telegram API"""
        
        # Конвертация UnifiedMessage в Telegram формат
        telegram_message = {
            "chat_id": int(chat_id),
            "text": message.text,
            "parse_mode": "HTML"
        }
        
        # Добавление inline клавиатуры
        if message.inline_keyboard:
            telegram_message["reply_markup"] = self._convert_inline_keyboard(
                message.inline_keyboard
            )
        
        # Отправка через Bot API
        response = await self._make_request(
            "POST", 
            "sendMessage", 
            data=telegram_message
        )
        
        return DeliveryResult(
            message_id=message.message_id,
            platform_message_id=str(response["result"]["message_id"]),
            success=True,
            status=DeliveryStatus.SENT
        )
    
    async def _extract_webhook_messages(
        self, 
        payload: dict[str, Any]
    ) -> list[UnifiedMessage]:
        """Извлечение сообщений из Telegram webhook"""
        
        messages = []
        
        if "message" in payload:
            tg_msg = payload["message"]
            
            unified_message = UnifiedMessage(
                message_id=str(uuid.uuid4()),
                platform="telegram",
                platform_message_id=str(tg_msg["message_id"]),
                user_id=str(tg_msg["from"]["id"]),
                chat_id=str(tg_msg["chat"]["id"]),
                text=tg_msg.get("text"),
                direction=MessageDirection.INBOUND
            )
            
            messages.append(unified_message)
        
        return messages
```

## 🔄 Webhook обработка

### Универсальная обработка webhook'ов:
```python
@router.post("/webhook/{platform}")
async def process_webhook(
    platform: str,
    request: Request,
    controller: MessagingController = Depends(get_messaging_controller)
):
    """Универсальный endpoint для всех платформ"""
    
    # Получение payload
    payload = await request.json()
    
    # Определение подписи по платформе
    signature = None
    if platform == "telegram":
        signature = request.headers.get("x-telegram-bot-api-secret-token")
    elif platform == "whatsapp":
        signature = request.headers.get("x-hub-signature-256")
    
    # Создание запроса
    webhook_request = WebhookRequest(
        platform=platform,
        payload=payload,
        signature=signature
    )
    
    # Обработка через контроллер
    return await controller.process_webhook(webhook_request)
```

### Автоматическая интеграция с диалогами:
```python
async def process_incoming_message(self, message: UnifiedMessage):
    """Автоматическая обработка входящего сообщения"""
    
    # NLP анализ
    nlp_result = await self.nlp_service.process_message(message.text)
    
    # Генерация ответа через AI
    ai_response = await self.conversation_service.process_conversation(
        user_id=message.user_id,
        session_id=message.chat_id,  # Используем chat_id как session_id
        message=message.text,
        intent=nlp_result.intent,
        entities=nlp_result.entities,
        platform=message.platform
    )
    
    # Отправка ответа обратно
    response_message = UnifiedMessage(
        message_id=str(uuid.uuid4()),
        platform=message.platform,
        chat_id=message.chat_id,
        text=ai_response.message,
        direction=MessageDirection.OUTBOUND
    )
    
    await self.messaging_service.send_message(
        platform=message.platform,
        chat_id=message.chat_id,
        message=response_message
    )
```

## 📊 Метрики и аналитика

### Отслеживаемые метрики:
- Время ответа AI
- Точность распознавания намерений  
- Количество эскалаций к операторам
- Удовлетворенность клиентов
- Статистика по платформам

### Структурированное логирование:
```python
logger.info(
    "Обработка сообщения",
    user_id=user_id,
    session_id=session_id,
    intent=intent,
    platform=platform.value
)
```

## 🧪 Тестирование

### Тестирование контроллеров:
- Мокирование сервисов
- Тестирование HTTP логики
- Валидация входа/выхода

### Тестирование сервисов:
- Мокирование репозиториев
- Тестирование бизнес-логики
- Интеграционные тесты

## 🔒 Безопасность

### Валидация входных данных:
- Очистка потенциально опасных символов
- Валидация форматов (email, phone, etc.)
- Ограничения размера и длины

### Audit логирование:
- Отслеживание действий пользователей
- Интеграции и их использование
- Безопасные операции с API ключами

## 💡 Лучшие практики

1. **Single Responsibility** - один класс = одна ответственность
2. **Dependency Inversion** - зависимость от абстракций
3. **Clean Code** - читаемый и поддерживаемый код
4. **Error Handling** - корректная обработка ошибок
5. **Testing** - покрытие тестами критичной логики
6. **Documentation** - документирование API и архитектуры

---

🤖 **Создано с помощью [Claude Code](https://claude.ai/code) для оптимальной архитектуры AI-платформы**