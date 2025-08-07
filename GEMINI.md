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

### Мессенджеры:
- **Telegram** - популярный мессенджер
- **WhatsApp Business** - бизнес коммуникации
- **VK** - российская социальная сеть
- **Viber** - мессенджер с бизнес-функциями

### Голосовые ассистенты:
- **Yandex Alice** - российский ассистент
- **Amazon Alexa** - международный стандарт
- **Google Assistant** - Google экосистема

## 🔄 Webhook обработка

### Универсальная обработка webhook'ов:
```python
async def handle_webhook(self, platform: str, payload: WebhookPayload):
    """Обработка входящих webhook'ов от всех платформ"""
    # Валидация платформы
    # Получение обработчика
    # Асинхронная обработка
    # Возврат результата
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