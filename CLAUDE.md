# Claude Code Инструкции для easy-flow

## 🏗️ Архитектура проекта

Проект следует принципам Clean Architecture с четко разделенными слоями:

### Структура слоев

```
app/
├── api/                    # Слой презентации (API)
│   ├── controllers/        # Контроллеры - только HTTP логика  
│   ├── routes/            # Маршруты FastAPI - тонкий слой
│   └── dependencies.py    # Dependency injection
├── services/              # Бизнес-логика
├── repositories/          # Слой данных
├── adapters/              # Внешние интеграции
└── models/                # Модели данных
```

## 🎯 Принципы разработки

### Контроллеры (Controllers)

**НЕ ДОЛЖНЫ содержать:**
- ❌ Бизнес-логику
- ❌ Прямые вызовы репозиториев
- ❌ Сложную обработку ошибок
- ❌ Оркестрацию сервисов

**ДОЛЖНЫ содержать только:**
- ✅ Валидацию входных данных HTTP
- ✅ Вызовы методов сервисов
- ✅ Форматирование HTTP ответов
- ✅ Обработку HTTP статус кодов

### Сервисы (Services)

**СОДЕРЖАТ:**
- ✅ Всю бизнес-логику
- ✅ Оркестрацию между репозиториями
- ✅ Валидацию бизнес-правил
- ✅ Интеграции с внешними сервисами

### Маршруты (Routes)

**Максимум 10 строк кода на endpoint:**
```python
@router.post("/chat")
async def process_chat_message(
    request: ChatRequest,
    controller: ConversationController = Depends(get_conversation_controller)
) -> ChatResponse:
    return await controller.process_chat_message(request)
```

## 🔧 Команды разработки

### Установка и запуск
```bash
# Установка зависимостей
make install

# Запуск в режиме разработки  
make dev

# Форматирование кода
make format

# Линтинг
make lint

# Тесты
make test
```

### Проверка качества кода
```bash
# Полная проверка перед коммитом
make check
```

## 🎮 Контроллеры API

### BaseController

Базовый класс для всех контроллеров:
- `handle_request()` - стандартная обработка с конвертацией ошибок
- `format_response()` - форматирование ответов
- `validate_id()` - валидация ID полей

### ConversationController

Контроллер для диалогов:
- `process_chat_message()` - обработка сообщений чата
- `get_user_sessions()` - получение сессий пользователя
- `get_session_history()` - история сообщений
- `escalate_to_human()` - эскалация к оператору

### IntegrationController

Контроллер интеграций:
- `connect_platform()` - подключение платформ
- `sync_platform_data()` - синхронизация данных
- `handle_webhook()` - обработка webhook'ов

### MessagingController

Контроллер мессенджеров - ТОЛЬКО HTTP логика:
- `send_message()` - отправка сообщений через платформы
- `process_webhook()` - обработка входящих webhook'ов
- `get_conversation_context()` - получение контекста диалога
- `update_conversation_context()` - обновление контекста диалога
- `get_platform_stats()` - статистика по платформам
- `list_supported_platforms()` - список поддерживаемых платформ

## 📝 Правила написания кода

### Валидация

**В контроллерах:** Только HTTP/API валидация
```python
def _validate_chat_request(self, request: ChatRequest) -> ChatRequest:
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")
    return request
```

**В сервисах:** Бизнес-валидация
```python
async def _validate_credentials(self, platform: str, credentials: dict) -> None:
    required_fields = self._get_required_fields(platform)
    if missing_fields := [f for f in required_fields if f not in credentials]:
        raise ValueError(f"Отсутствуют поля: {', '.join(missing_fields)}")
```

### Обработка ошибок

**Контроллеры:** Конвертируют в HTTP ошибки
```python
async def handle_request(self, request_func, *args, **kwargs) -> Any:
    try:
        return await request_func(*args, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Ошибка валидации: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
```

**Сервисы:** Выбрасывают доменные исключения
```python
async def process_conversation(self, user_id: str, message: str) -> ConversationResult:
    if not user_id:
        raise ValueError("User ID обязателен")
    # бизнес-логика
```

## 🔗 Dependency Injection

### Регистрация зависимостей

```python
# app/api/dependencies.py

def get_conversation_controller() -> ConversationController:
    return ConversationController(
        conversation_service=get_conversation_service(),
        nlp_service=get_nlp_service()
    )
```

### Использование в маршрутах

```python
@router.post("/chat")
async def process_chat_message(
    request: ChatRequest,
    controller: ConversationController = Depends(get_conversation_controller)
) -> ChatResponse:
    return await controller.process_chat_message(request)
```

## 🧪 Тестирование

### Тестирование контроллеров

```python
def test_process_chat_message():
    # Мокируем сервисы
    mock_conversation_service = Mock()
    mock_nlp_service = Mock()
    
    controller = ConversationController(
        conversation_service=mock_conversation_service,
        nlp_service=mock_nlp_service
    )
    
    # Тестируем только логику контроллера
    assert controller.validate_id("valid_id") == "valid_id"
```

### Тестирование сервисов

```python
async def test_conversation_service():
    # Мокируем репозитории
    mock_user_repo = Mock()
    mock_conversation_repo = Mock()
    
    service = ConversationService(
        user_repository=mock_user_repo,
        conversation_repository=mock_conversation_repo
    )
    
    # Тестируем бизнес-логику
    result = await service.process_conversation("user123", "session456", "Hello")
    assert result.response is not None
```

## 📊 Мониторинг и логирование

### Структурированное логирование

```python
import structlog

logger = structlog.get_logger()

# В сервисах
logger.info(
    "Обработка сообщения",
    user_id=user_id,
    session_id=session_id,
    intent=intent
)

# В контроллерах (только критические ошибки)
logger.error(
    "Неожиданная ошибка в контроллере", 
    error=str(e),
    controller=self.__class__.__name__
)
```

## 🚀 Развертывание

### Pre-commit хуки

```bash
# Установка
pre-commit install

# Проверка всех файлов
pre-commit run --all-files
```

### Docker

```bash
# Сборка
docker build -t easy-flow .

# Запуск
docker-compose up -d
```

## 📱 Архитектура мессенджеров

Модуль мессенджеров следует принципам Clean Architecture с четким разделением ответственности.

### Структура мессенджеров

```
app/
├── api/
│   ├── controllers/
│   │   └── messaging_controller.py    # HTTP логика мессенджеров
│   └── routes/
│       └── messaging.py               # Маршруты API
├── services/
│   └── messaging_service.py           # Бизнес-логика мессенджеров
├── adapters/
│   └── messaging/                     # Адаптеры платформ
│       ├── base.py                    # Базовый класс адаптера
│       ├── telegram.py                # Telegram Bot API
│       ├── whatsapp.py                # WhatsApp Business API
│       ├── vk.py                      # VK Bot API
│       └── viber.py                   # Viber Bot API
└── models/
    └── messaging.py                   # Модели сообщений
```

### MessagingController - Принципы

**НЕ ДОЛЖЕН содержать:**
- ❌ Логику обработки сообщений
- ❌ Создание адаптеров платформ
- ❌ Бизнес-правила маршрутизации
- ❌ Конвертацию между форматами сообщений

**ДОЛЖЕН содержать только:**
- ✅ HTTP валидацию запросов
- ✅ Делегирование в MessagingService
- ✅ Форматирование HTTP ответов
- ✅ Обработку HTTP статусов

### MessagingController - Пример

```python
class MessagingController(BaseController):
    """Контроллер мессенджеров - ТОЛЬКО HTTP логика."""
    
    def __init__(self, messaging_service: MessagingService):
        super().__init__()
        self.messaging_service = messaging_service

    async def send_message(self, request: SendMessageRequest) -> SendMessageResponse:
        """Отправка сообщения - только валидация и делегирование."""
        return await self.handle_request(
            self._send_message_impl,
            request
        )

    async def _send_message_impl(self, request: SendMessageRequest) -> SendMessageResponse:
        # ✅ Валидация HTTP входных данных
        validated_request = self._validate_send_message_request(request)
        
        # ✅ Создание доменной модели
        message = UnifiedMessage(
            message_id=str(uuid.uuid4()),
            platform=validated_request.platform,
            chat_id=validated_request.chat_id,
            text=validated_request.text,
            message_type=validated_request.message_type
        )
        
        # ✅ Делегирование бизнес-логики сервису
        result = await self.messaging_service.send_message(
            platform=validated_request.platform,
            chat_id=validated_request.chat_id,
            message=message,
            priority=validated_request.priority
        )
        
        # ✅ Форматирование HTTP ответа
        return SendMessageResponse(
            success=result.success,
            message_id=result.message_id,
            delivery_status=result.status.value
        )

    def _validate_send_message_request(self, request: SendMessageRequest) -> SendMessageRequest:
        """HTTP валидация - проверка формата и обязательных полей."""
        if not request.platform or not request.platform.strip():
            raise HTTPException(status_code=400, detail="Platform name is required")
            
        if not request.chat_id or not request.chat_id.strip():
            raise HTTPException(status_code=400, detail="Chat ID is required")
            
        if request.message_type == MessageType.TEXT:
            if not request.text or not request.text.strip():
                raise HTTPException(status_code=400, detail="Text content is required")
                
        return request
```

### MessagingService - Бизнес-логика

**СОДЕРЖИТ всю бизнес-логику:**
- ✅ Управление адаптерами платформ
- ✅ Регистрацию платформ
- ✅ Маршрутизацию сообщений
- ✅ Обработку webhook'ов
- ✅ Управление контекстом диалогов
- ✅ Сбор статистики

```python
class MessagingService:
    """Сервис мессенджеров - ВСЯ бизнес-логика здесь."""
    
    def __init__(self, integration_repository: IntegrationRepository):
        self.integration_repository = integration_repository
        self._adapters: dict[str, MessagingAdapter] = {}
        self._platform_configs: dict[str, PlatformConfig] = {}

    async def send_message(
        self, 
        platform: str, 
        chat_id: str, 
        message: UnifiedMessage,
        priority: int = 0
    ) -> DeliveryResult:
        """Отправка сообщения - вся бизнес-логика."""
        
        # Получение адаптера платформы
        adapter = self._adapters.get(platform)
        if not adapter:
            raise ValueError(f"Platform {platform} not registered")
        
        # Проверка совместимости платформы с сообщением
        if message.platform != platform:
            message.platform = platform
            
        # Отправка через адаптер
        result = await adapter.send_message(chat_id, message, priority)
        
        logger.info(
            "Message sent via messaging service",
            platform=platform,
            success=result.success,
            message_id=result.message_id
        )
        
        return result

    async def process_webhook(
        self,
        platform: str,
        payload: dict[str, Any],
        signature: str | None = None
    ) -> WebhookProcessingResult:
        """Обработка webhook - извлечение и нормализация сообщений."""
        
        adapter = self._adapters.get(platform)
        if not adapter:
            raise ValueError(f"Platform {platform} not registered")
            
        # Извлечение сообщений через адаптер
        messages = await adapter.receive_webhook(payload, signature)
        
        # В будущем: интеграция с conversation service
        # для автоматической обработки входящих сообщений
        
        return WebhookProcessingResult(
            event_id=str(uuid.uuid4()),
            platform=platform,
            success=True,
            messages=messages
        )
```

### Platform Adapters - Паттерн адаптера

**Базовый MessagingAdapter:**
- ✅ Общая логика rate limiting
- ✅ Статистика сообщений
- ✅ Webhook обработка
- ✅ Унификация интерфейсов

**Platform-specific adapters:**
- ✅ Конвертация UnifiedMessage в платформенный формат
- ✅ Извлечение сообщений из webhook'ов
- ✅ Верификация подписей
- ✅ Особенности платформы

```python
class TelegramAdapter(MessagingAdapter):
    """Telegram-специфичная реализация."""
    
    async def _send_platform_message(
        self, 
        chat_id: str, 
        message: UnifiedMessage
    ) -> DeliveryResult:
        """Отправка через Telegram Bot API."""
        
        try:
            # Конвертация в Telegram формат
            telegram_message = self._convert_to_telegram_format(message)
            
            # Отправка через Bot API
            sent_message = await self.bot.send_message(
                chat_id=int(chat_id),
                text=telegram_message["text"],
                reply_markup=telegram_message.get("reply_markup"),
                parse_mode=ParseMode.HTML
            )
            
            return DeliveryResult(
                message_id=message.message_id,
                platform_message_id=str(sent_message.message_id),
                platform="telegram",
                status=DeliveryStatus.SENT,
                success=True,
                sent_at=datetime.now()
            )
            
        except TelegramError as e:
            return DeliveryResult(
                message_id=message.message_id,
                platform="telegram", 
                status=DeliveryStatus.FAILED,
                success=False,
                error_message=str(e)
            )

    async def _extract_webhook_messages(
        self, 
        payload: dict[str, Any]
    ) -> list[UnifiedMessage]:
        """Извлечение сообщений из Telegram webhook."""
        
        messages = []
        
        if "message" in payload:
            tg_message = payload["message"]
            
            # Конвертация в UnifiedMessage
            unified_message = UnifiedMessage(
                message_id=str(uuid.uuid4()),
                platform="telegram",
                platform_message_id=str(tg_message["message_id"]),
                user_id=str(tg_message["from"]["id"]),
                chat_id=str(tg_message["chat"]["id"]),
                text=tg_message.get("text"),
                message_type=MessageType.TEXT,
                direction=MessageDirection.INBOUND,
                timestamp=datetime.now()
            )
            
            messages.append(unified_message)
            
        return messages
```

### Dependency Injection для мессенджеров

```python
# app/api/dependencies.py

def get_messaging_controller() -> MessagingController:
    """Фабрика MessagingController с инъекцией зависимостей."""
    return MessagingController(
        messaging_service=get_messaging_service()
    )

def get_messaging_service() -> MessagingService:
    """Фабрика MessagingService."""
    return MessagingService(
        integration_repository=get_integration_repository()
    )
```

### Маршруты мессенджеров - Тонкий слой

```python
# app/api/routes/messaging.py

@router.post("/send", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    controller: MessagingController = Depends(get_messaging_controller)
) -> SendMessageResponse:
    """Отправка сообщения - максимум 5 строк."""
    return await controller.send_message(request)

@router.post("/webhook/{platform}", response_model=WebhookResponse)
async def process_webhook(
    platform: str,
    request: Request,
    controller: MessagingController = Depends(get_messaging_controller)
) -> WebhookResponse:
    """Обработка webhook - делегирование контроллеру."""
    payload = await request.json()
    webhook_request = WebhookRequest(platform=platform, payload=payload)
    return await controller.process_webhook(webhook_request)
```

### Unified Message Model

```python
class UnifiedMessage(BaseModel):
    """Унифицированная модель сообщения."""
    
    message_id: str                        # Внутренний ID
    platform: str                         # Платформа (telegram, whatsapp, etc.)
    platform_message_id: str              # ID в платформе
    user_id: str                          # ID пользователя
    chat_id: str                          # ID чата/диалога
    
    text: str | None = None               # Текст сообщения
    message_type: MessageType = MessageType.TEXT
    direction: MessageDirection = MessageDirection.OUTBOUND
    
    # Интерактивные элементы
    inline_keyboard: InlineKeyboard | None = None
    reply_keyboard: ReplyKeyboard | None = None
    
    # Медиа
    attachments: list[MessageAttachment] = []
    
    # Метаданные
    reply_to_message_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = {}
```

### Тестирование мессенджеров

**Тестирование контроллера:**
```python
async def test_messaging_controller_send_message():
    # Мок сервиса
    mock_service = Mock(spec=MessagingService)
    mock_service.send_message.return_value = DeliveryResult(
        message_id="123",
        platform="telegram",
        success=True,
        status=DeliveryStatus.SENT
    )
    
    # Создание контроллера
    controller = MessagingController(messaging_service=mock_service)
    
    # Тест HTTP логики
    request = SendMessageRequest(
        platform="telegram",
        chat_id="123",
        text="Test message"
    )
    
    response = await controller.send_message(request)
    
    # Проверка HTTP ответа
    assert response.success is True
    assert response.message_id == "123"
    
    # Проверка вызова сервиса
    mock_service.send_message.assert_called_once()
```

**Тестирование сервиса:**
```python
async def test_messaging_service_send_message():
    # Мок адаптера
    mock_adapter = Mock(spec=TelegramAdapter)
    mock_adapter.send_message.return_value = DeliveryResult(
        message_id="123",
        platform="telegram", 
        success=True,
        status=DeliveryStatus.SENT
    )
    
    # Сервис с мок адаптером
    service = MessagingService(integration_repository=Mock())
    service._adapters["telegram"] = mock_adapter
    
    # Тест бизнес-логики
    message = UnifiedMessage(
        message_id="123",
        platform="telegram",
        chat_id="456",
        text="Test"
    )
    
    result = await service.send_message("telegram", "456", message)
    
    # Проверка результата
    assert result.success is True
    assert result.message_id == "123"
    
    # Проверка вызова адаптера
    mock_adapter.send_message.assert_called_once_with("456", message, 0)
```

## 🎤 Архитектура голосовых ассистентов

Модуль голосовых ассистентов реализован согласно принципам Clean Architecture с полным разделением ответственности.

### Структура голосовых интеграций

```
app/
├── api/
│   ├── controllers/
│   │   └── voice_controller.py        # HTTP логика голосовых запросов
│   └── routes/
│       └── voice.py                   # API маршруты голосовых endpoints
├── services/
│   └── voice_service.py               # Бизнес-логика голосовых взаимодействий
├── adapters/
│   └── voice/                         # Адаптеры голосовых платформ
│       ├── base.py                    # Базовый класс голосового адаптера
│       ├── yandex_alice.py           # Yandex Alice интеграция
│       ├── amazon_alexa.py           # Amazon Alexa (планируется)
│       ├── google_assistant.py       # Google Assistant (планируется)
│       └── apple_siri.py             # Apple Siri (планируется)
└── models/
    └── voice.py                      # Модели голосовых сообщений
```

### VoiceController - Принципы

**НЕ ДОЛЖЕН содержать:**
- ❌ Логику обработки голосовых сообщений
- ❌ Создание голосовых адаптеров
- ❌ Бизнес-правила распознавания намерений
- ❌ Конвертацию между форматами голосовых платформ

**ДОЛЖЕН содержать только:**
- ✅ HTTP валидацию webhook запросов
- ✅ Делегирование в VoiceService
- ✅ Форматирование HTTP ответов
- ✅ Обработку HTTP статусов

### VoiceController - Пример

```python
class VoiceController(BaseController):
    """Контроллер голосовых ассистентов - ТОЛЬКО HTTP логика."""
    
    def __init__(self, voice_service: VoiceService):
        super().__init__()
        self.voice_service = voice_service

    async def process_webhook(self, request: VoiceWebhookRequest) -> VoiceWebhookResponse:
        """Обработка голосового webhook - только валидация и делегирование."""
        return await self.handle_request(
            self._process_webhook_impl,
            request
        )

    async def _process_webhook_impl(self, request: VoiceWebhookRequest) -> VoiceWebhookResponse:
        # ✅ HTTP валидация входных данных
        validated_request = self._validate_webhook_request(request)
        
        # ✅ Конвертация platform string в enum
        platform = self._parse_voice_platform(validated_request.platform)
        
        # ✅ Делегирование бизнес-логики сервису
        result = await self.voice_service.process_voice_webhook(
            platform=platform,
            request_data=validated_request.payload,
            signature=validated_request.signature
        )
        
        # ✅ Форматирование HTTP ответа
        return VoiceWebhookResponse(
            success=result.success,
            event_id=result.event_id,
            platform=result.platform.value,
            response=result.response,
            error=result.error
        )

    def _validate_webhook_request(self, request: VoiceWebhookRequest) -> VoiceWebhookRequest:
        """HTTP валидация webhook запроса."""
        if not request.platform or not request.platform.strip():
            raise HTTPException(status_code=400, detail="Platform name is required")
            
        if not isinstance(request.payload, dict) or not request.payload:
            raise HTTPException(status_code=400, detail="Payload must be a valid JSON object")
            
        return request
```

### VoiceService - Бизнес-логика

**СОДЕРЖИТ всю бизнес-логику:**
- ✅ Управление голосовыми адаптерами
- ✅ Регистрацию голосовых платформ
- ✅ Обработку voice webhook'ов
- ✅ Маппинг намерений на бизнес-действия
- ✅ Управление голосовыми сессиями
- ✅ Сбор аналитики голосовых взаимодействий

```python
class VoiceService:
    """Сервис голосовых ассистентов - ВСЯ бизнес-логика здесь."""
    
    def __init__(self, integration_repository: IntegrationRepository):
        self.integration_repository = integration_repository
        self._adapters: dict[VoicePlatform, VoiceAdapter] = {}
        self._platform_configs: dict[VoicePlatform, VoicePlatformConfig] = {}
        self._intent_mappings: dict[str, VoiceIntentMapping] = {}

    async def process_voice_webhook(
        self,
        platform: VoicePlatform,
        request_data: dict[str, Any],
        signature: str | None = None
    ) -> VoiceWebhookProcessingResult:
        """Обработка voice webhook - вся бизнес-логика."""
        
        # Получение адаптера платформы
        adapter = self._adapters.get(platform)
        if not adapter:
            raise ValueError(f"Voice platform {platform.value} not registered")
        
        # Обработка через адаптер
        voice_response = await adapter.process_voice_request(request_data, signature)
        
        # Форматирование ответа для платформы  
        formatted_response = await adapter.format_voice_response(voice_response)
        
        return VoiceWebhookProcessingResult(
            event_id=str(uuid.uuid4()),
            platform=platform,
            success=True,
            response=formatted_response
        )
```

### Voice Adapters - Паттерн адаптера

**Базовый VoiceAdapter:**
- ✅ Общая логика session management
- ✅ Аналитика голосовых взаимодействий  
- ✅ Health check и мониторинг
- ✅ Унификация интерфейсов

**Platform-specific adapters:**
- ✅ Конвертация VoiceMessage в платформенный формат
- ✅ Извлечение намерений и сущностей из запросов
- ✅ Верификация подписей webhook'ов
- ✅ Особенности конкретной платформы

```python
class YandexAliceAdapter(VoiceAdapter):
    """Yandex Alice специфичная реализация."""
    
    async def process_voice_request(
        self,
        request_data: dict[str, Any],
        signature: str | None = None
    ) -> VoiceResponse:
        """Обработка Alice запроса."""
        
        try:
            # Верификация подписи если требуется
            if self.config.verify_webhooks and signature:
                is_valid = await self.verify_request_signature(request_data, signature)
                if not is_valid:
                    raise ValueError("Invalid request signature")
            
            # Извлечение голосового сообщения
            voice_message = await self.extract_voice_message(request_data)
            
            # Получение или создание сессии
            session = await self._get_or_create_session(request_data)
            
            # Генерация ответа через бизнес-логику
            response = await self._generate_response(voice_message, session)
            
            return response
            
        except Exception as e:
            # Обработка ошибок и возврат graceful ответа
            return VoiceResponse(
                text="Извините, произошла ошибка. Попробуйте ещё раз.",
                speech="Извините, произошла ошибка. Попробуйте ещё раз.",
                should_end_session=False
            )

    async def extract_voice_message(self, request_data: dict[str, Any]) -> VoiceMessage:
        """Извлечение унифицированного голосового сообщения из Alice запроса."""
        request = request_data.get("request", {})
        session = request_data.get("session", {})
        
        # Извлечение намерений и сущностей
        intent = None
        entities = []
        
        if "nlu" in request:
            nlu = request["nlu"]
            
            # Извлечение намерения с наивысшим confidence
            if "intents" in nlu and nlu["intents"]:
                intent_data = max(
                    nlu["intents"].items(),
                    key=lambda x: x[1].get("slots", {}).get("confidence", 0.0)
                )
                
                intent = VoiceIntent(
                    name=intent_data[0],
                    confidence=intent_data[1].get("slots", {}).get("confidence", 0.0),
                    entities=intent_data[1].get("slots", {})
                )
        
        return VoiceMessage(
            platform=VoicePlatform.YANDEX_ALICE,
            platform_message_id=request.get("request_id", ""),
            session_id=session.get("session_id", ""),
            user_id=session.get("user_id", ""),
            text=request.get("original_utterance"),
            intent=intent,
            entities=entities
        )
```

### Dependency Injection для голосовых ассистентов

```python
# app/api/dependencies.py

def get_voice_controller() -> VoiceController:
    """Фабрика VoiceController с инъекцией зависимостей."""
    return VoiceController(
        voice_service=get_voice_service()
    )

def get_voice_service() -> VoiceService:
    """Фабрика VoiceService."""
    return VoiceService(
        integration_repository=get_integration_repository()
    )
```

### Маршруты голосовых ассистентов - Тонкий слой

```python
# app/api/routes/voice.py

@router.post("/webhook/{platform}", response_model=VoiceWebhookResponse)
async def process_voice_webhook(
    platform: str,
    request: Request,
    controller: VoiceController = Depends(get_voice_controller)
) -> VoiceWebhookResponse:
    """Обработка голосового webhook - максимум 10 строк."""
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
    """Yandex Alice специальный endpoint - делегирование контроллеру."""
    payload = await request.json()
    signature = request.headers.get("X-Hub-Signature")
    
    webhook_request = VoiceWebhookRequest(
        platform="yandex_alice",
        payload=payload,
        signature=signature
    )
    
    result = await controller.process_webhook(webhook_request)
    
    # Возврат Alice-форматированного ответа
    if result.success and result.response:
        return result.response
    else:
        return {
            "version": "1.0",
            "response": {
                "text": "Извините, произошла ошибка. Попробуйте позже.",
                "end_session": True
            }
        }
```

### Unified Voice Models

```python
class VoiceMessage(BaseModel):
    """Унифицированное голосовое сообщение."""
    
    # Core fields
    message_id: str
    platform: VoicePlatform  # yandex_alice, amazon_alexa, google_assistant, apple_siri
    session_id: str
    user_id: str
    
    # Content
    text: str | None                    # Распознанный текст
    speech_text: str | None             # Текст для синтеза речи
    
    # NLU результаты
    intent: VoiceIntent | None          # Распознанное намерение
    entities: list[VoiceEntity]         # Извлеченные сущности
    
    # Rich content
    card: VoiceCard | None              # Карточка для устройств с экраном
    directives: list[VoiceDirective]    # Платформо-специфичные директивы
    
    # Session management
    should_end_session: bool = False
    expects_user_input: bool = True

class VoiceResponse(BaseModel):
    """Ответ голосового ассистента."""
    
    text: str | None                    # Текстовый ответ
    speech: str | None                  # Речевой синтез
    card: VoiceCard | None              # Rich карточка
    directives: list[VoiceDirective]    # Специальные команды
    should_end_session: bool = False
    session_attributes: dict[str, Any]  # Данные сессии для сохранения
```

### Тестирование голосовых интеграций

**Тестирование контроллера:**
```python
async def test_voice_controller_process_webhook():
    # Мок сервиса
    mock_service = Mock(spec=VoiceService)
    mock_service.process_voice_webhook.return_value = VoiceWebhookProcessingResult(
        event_id="test-event-123",
        platform=VoicePlatform.YANDEX_ALICE,
        success=True,
        response={"version": "1.0", "response": {"text": "Test response"}}
    )
    
    # Создание контроллера
    controller = VoiceController(voice_service=mock_service)
    
    # Тест HTTP логики
    request = VoiceWebhookRequest(
        platform="yandex_alice",
        payload={"request": {"original_utterance": "Test"}},
        signature="test-signature"
    )
    
    response = await controller.process_webhook(request)
    
    # Проверка HTTP ответа
    assert response.success is True
    assert response.platform == "yandex_alice"
    
    # Проверка вызова сервиса
    mock_service.process_voice_webhook.assert_called_once()
```

## 📚 Дополнительные ресурсы

- [Clean Architecture Principles](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Dependency Injection in FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [WhatsApp Business Platform](https://developers.facebook.com/docs/whatsapp)
- [Yandex Alice Skills](https://yandex.ru/dev/dialogs/)
- [Amazon Alexa Skills Kit](https://developer.amazon.com/en-US/alexa/alexa-skills-kit)
- [Google Actions](https://developers.google.com/assistant)

---

**Важно:** Всегда следуй принципу единой ответственности. Каждый класс и функция должны иметь одну причину для изменения.