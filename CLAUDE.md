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

## 📚 Дополнительные ресурсы

- [Clean Architecture Principles](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Dependency Injection in FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/)

---

**Важно:** Всегда следуй принципу единой ответственности. Каждый класс и функция должны иметь одну причину для изменения.