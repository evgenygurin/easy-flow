# 🏗️ Архитектура системы Easy Flow

## Обзор архитектуры

Easy Flow построен на принципах **Clean Architecture** с четким разделением ответственности и слоев абстракции.

### Диаграмма высокого уровня

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Client    │    │  Mobile Apps    │    │  Messengers     │
│   (React/Vue)   │    │ (iOS/Android)   │    │ (TG/WA/VK)      │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
        ┌──────────────────────────────────────────────────────┐
        │                 API Gateway                          │
        │              (FastAPI + Routes)                      │
        └──────────────────────┬───────────────────────────────┘
                               │
        ┌──────────────────────────────────────────────────────┐
        │               Controllers Layer                       │
        │    (HTTP Logic, Validation, Response Formatting)     │
        └──────────────────────┬───────────────────────────────┘
                               │
        ┌──────────────────────────────────────────────────────┐
        │              Business Logic Layer                    │
        │     (Services: Conversation, NLP, AI, Messaging)    │
        └─────────┬────────────┬────────────┬───────────┬──────┘
                  │            │            │           │
        ┌─────────▼───┐ ┌──────▼────┐ ┌─────▼────┐ ┌───▼────┐
        │ Repository  │ │ Adapters  │ │ External │ │ Cache  │
        │   Layer     │ │  Layer    │ │   APIs   │ │ (Redis)│
        │(PostgreSQL) │ │(Platforms)│ │(AI/ML)   │ │        │
        └─────────────┘ └───────────┘ └──────────┘ └────────┘
```

## Слои архитектуры

### 1. Presentation Layer (API)

**Расположение**: `app/api/`

#### Controllers (`app/api/controllers/`)
- **BaseController**: Базовая функциональность для всех контроллеров
- **ConversationController**: Управление диалогами с AI
- **MessagingController**: Отправка и получение сообщений
- **IntegrationController**: Управление интеграциями платформ

**Принципы контроллеров:**
```python
# ✅ Правильно - только HTTP логика
class MessagingController(BaseController):
    async def send_message(self, request: SendMessageRequest) -> SendMessageResponse:
        validated_request = self._validate_request(request)  # HTTP валидация
        result = await self.messaging_service.send_message(validated_request)  # Делегирование
        return self._format_response(result)  # HTTP форматирование

# ❌ Неправильно - бизнес-логика в контроллере
class MessagingController:
    async def send_message(self, request):
        # Создание адаптера платформы - это бизнес-логика!
        adapter = TelegramAdapter(token=request.token)
        # Конвертация сообщения - это бизнес-логика!
        telegram_message = convert_to_telegram_format(request.message)
```

#### Routes (`app/api/routes/`)
- **Максимум 10 строк** на endpoint
- Только маршрутизация и валидация параметров
- Делегирование контроллерам

```python
@router.post("/chat")
async def process_chat_message(
    request: ChatRequest,
    controller: ConversationController = Depends(get_conversation_controller)
) -> ChatResponse:
    return await controller.process_chat_message(request)
```

### 2. Business Logic Layer (Services)

**Расположение**: `app/services/`

#### Основные сервисы

##### ConversationService
```python
class ConversationService:
    """Управление диалогами и AI взаимодействиями."""
    
    async def process_conversation(
        self, user_id: str, session_id: str, message: str
    ) -> ConversationResult:
        # Получение контекста диалога
        context = await self.conversation_repository.get_context(session_id)
        
        # NLP анализ сообщения
        nlp_result = await self.nlp_service.analyze_message(message)
        
        # Генерация ответа через AI
        ai_response = await self.ai_service.generate_response(
            message, context, nlp_result
        )
        
        # Сохранение в базу
        await self.conversation_repository.save_message(...)
        
        return ConversationResult(response=ai_response, intent=nlp_result.intent)
```

##### MessagingService
```python
class MessagingService:
    """Управление отправкой сообщений через разные платформы."""
    
    def __init__(self, integration_repository: IntegrationRepository):
        self._adapters: dict[str, MessagingAdapter] = {}
        self._register_adapters()
    
    async def send_message(
        self, platform: str, chat_id: str, message: UnifiedMessage
    ) -> DeliveryResult:
        adapter = self._get_adapter(platform)
        return await adapter.send_message(chat_id, message)
```

##### IntegrationService
```python
class IntegrationService:
    """Управление интеграциями с внешними платформами."""
    
    async def connect_platform(
        self, user_id: str, platform: str, credentials: dict
    ) -> ConnectionResult:
        # Валидация учетных данных
        await self._validate_credentials(platform, credentials)
        
        # Создание подключения
        connection = await self._create_connection(platform, credentials)
        
        # Сохранение в базе
        await self.integration_repository.save_connection(user_id, connection)
        
        return ConnectionResult(success=True, platform_id=connection.id)
```

### 3. Data Access Layer (Repositories)

**Расположение**: `app/repositories/`

#### Repository Pattern

##### Интерфейсы (`app/repositories/interfaces/`)
```python
class ConversationRepository(ABC):
    @abstractmethod
    async def get_session_history(
        self, session_id: str, limit: int = 50
    ) -> list[Message]:
        pass
    
    @abstractmethod
    async def save_message(self, message: Message) -> str:
        pass
```

##### Реализации (`app/repositories/sqlalchemy/`)
```python
class SQLAlchemyConversationRepository(ConversationRepository):
    async def get_session_history(
        self, session_id: str, limit: int = 50
    ) -> list[Message]:
        async with self.session() as session:
            result = await session.execute(
                select(MessageModel)
                .where(MessageModel.session_id == session_id)
                .order_by(MessageModel.created_at.desc())
                .limit(limit)
            )
            return [self._to_domain_model(row) for row in result.scalars()]
```

### 4. External Adapters Layer

**Расположение**: `app/adapters/`

#### Messaging Adapters
```python
class MessagingAdapter(ABC):
    """Базовый класс для адаптеров мессенджеров."""
    
    @abstractmethod
    async def send_message(
        self, chat_id: str, message: UnifiedMessage, priority: int = 0
    ) -> DeliveryResult:
        pass
    
    @abstractmethod
    async def receive_webhook(
        self, payload: dict[str, Any], signature: str | None = None
    ) -> list[UnifiedMessage]:
        pass

class TelegramAdapter(MessagingAdapter):
    """Telegram-специфичная реализация."""
    
    async def send_message(
        self, chat_id: str, message: UnifiedMessage, priority: int = 0
    ) -> DeliveryResult:
        # Конвертация в Telegram формат
        telegram_message = self._convert_to_telegram_format(message)
        
        # Отправка через Bot API
        sent_message = await self.bot.send_message(
            chat_id=int(chat_id),
            text=telegram_message["text"],
            reply_markup=telegram_message.get("reply_markup"),
        )
        
        return DeliveryResult(
            message_id=message.message_id,
            platform_message_id=str(sent_message.message_id),
            platform="telegram",
            status=DeliveryStatus.SENT,
            success=True,
        )
```

#### E-commerce Adapters
```python
class EcommerceAdapter(ABC):
    """Базовый класс для e-commerce интеграций."""
    
    @abstractmethod
    async def get_orders(
        self, user_credentials: dict, filters: OrderFilters
    ) -> list[Order]:
        pass

class WildberriesAdapter(EcommerceAdapter):
    async def get_orders(
        self, user_credentials: dict, filters: OrderFilters
    ) -> list[Order]:
        # Специфичная реализация для Wildberries API
        pass
```

## Domain Models

**Расположение**: `app/models/`

### UnifiedMessage
```python
class UnifiedMessage(BaseModel):
    """Унифицированная модель сообщения для всех платформ."""
    
    message_id: str
    platform: str  # telegram, whatsapp, vk, viber
    platform_message_id: str
    user_id: str
    chat_id: str
    
    text: str | None = None
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

### ConversationContext
```python
class ConversationContext(BaseModel):
    session_id: str
    user_id: str
    platform: str
    current_state: str
    context_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime
```

## Dependency Injection

**Расположение**: `app/api/dependencies.py`

```python
def get_conversation_controller() -> ConversationController:
    return ConversationController(
        conversation_service=get_conversation_service(),
        nlp_service=get_nlp_service(),
    )

def get_conversation_service() -> ConversationService:
    return ConversationService(
        conversation_repository=get_conversation_repository(),
        nlp_service=get_nlp_service(),
        ai_service=get_ai_service(),
    )

def get_conversation_repository() -> ConversationRepository:
    return SQLAlchemyConversationRepository(
        session_factory=get_database_session_factory()
    )
```

## Паттерны проектирования

### 1. Repository Pattern
- Абстракция доступа к данным
- Возможность замены источника данных
- Упрощение тестирования

### 2. Adapter Pattern
- Унификация интерфейсов внешних сервисов
- Легкое добавление новых платформ
- Инкапсуляция специфичной логики

### 3. Dependency Injection
- Слабая связанность компонентов
- Простота тестирования
- Гибкость конфигурации

### 4. Strategy Pattern
- Выбор алгоритмов обработки во время выполнения
- Используется в AI Service для выбора модели

### 5. Chain of Responsibility
- Обработка сообщений в NLP Service
- Последовательная обработка через цепочку анализаторов

## Принципы SOLID

### Single Responsibility Principle (SRP)
- Каждый контроллер отвечает только за HTTP логику
- Каждый сервис имеет одну бизнес-область
- Репозитории отвечают только за доступ к данным

### Open/Closed Principle (OCP)
- Новые платформы добавляются через интерфейсы адаптеров
- Расширение функциональности без изменения существующего кода

### Liskov Substitution Principle (LSP)
- Все адаптеры мессенджеров взаимозаменяемы
- Репозитории можно заменить без изменения бизнес-логики

### Interface Segregation Principle (ISP)
- Разные интерфейсы для разных типов репозиториев
- Специфичные контракты для каждого типа адаптера

### Dependency Inversion Principle (DIP)
- Высокоуровневые модули не зависят от низкоуровневых
- Зависимость от абстракций, а не от конкретных реализаций

## Масштабирование архитектуры

### Горизонтальное масштабирование
- Stateless сервисы
- Использование Redis для сессий
- Микросервисная готовность

### Производительность
- Асинхронная обработка (async/await)
- Кэширование частых запросов в Redis
- Connection pooling для базы данных

### Мониторинг и наблюдаемость
- Структурированные логи (structlog)
- Метрики Prometheus
- Health checks

---

🤖 Создано с помощью [Claude Code](https://claude.ai/code)