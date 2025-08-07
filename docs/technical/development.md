# 💻 Руководство по разработке

## Настройка среды разработки

### Системные требования

- **Python 3.12+**
- **PostgreSQL 15+**  
- **Redis 7+**
- **uv** (рекомендуется) или pip
- **Docker & Docker Compose** (опционально)
- **Git**

### Первоначальная настройка

#### 1. Клонирование репозитория
```bash
git clone https://github.com/evgenygurin/easy-flow.git
cd easy-flow
```

#### 2. Установка uv (рекомендуется)
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Или через pip
pip install uv
```

#### 3. Установка зависимостей
```bash
# С uv (рекомендуется)
uv sync

# Или с pip
pip install -r requirements.txt
```

#### 4. Настройка переменных окружения
```bash
# Скопируйте файл примера
cp .env.example .env

# Отредактируйте .env файл
vim .env
```

#### 5. Настройка базы данных
```bash
# Запуск PostgreSQL и Redis в Docker
docker-compose up -d postgres redis

# Или локально
# PostgreSQL: createdb easyflow
# Redis: redis-server

# Применение миграций
uv run alembic upgrade head
```

### Конфигурация .env файла

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/easyflow
REDIS_URL=redis://localhost:6379/0

# AI Services
OPENAI_API_KEY=sk-your-openai-api-key
YANDEX_GPT_API_KEY=your-yandex-gpt-key
YANDEX_GPT_FOLDER_ID=your-folder-id

# E-commerce Platforms
WILDBERRIES_API_KEY=your-wb-api-key
OZON_CLIENT_ID=your-ozon-client-id
OZON_API_KEY=your-ozon-api-key

# Messaging Platforms
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_WEBHOOK_SECRET=your-webhook-secret

WHATSAPP_ACCESS_TOKEN=your-whatsapp-token
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id
WHATSAPP_WEBHOOK_VERIFY_TOKEN=your-verify-token

VK_ACCESS_TOKEN=your-vk-access-token
VK_GROUP_ID=your-group-id
VK_SECRET_KEY=your-secret-key

VIBER_AUTH_TOKEN=your-viber-auth-token

# Security
SECRET_KEY=your-super-secret-key-here-32-chars-min
ENCRYPTION_KEY=your-encryption-key-for-credentials

# Development
DEBUG=true
LOG_LEVEL=DEBUG
```

## Команды разработки

### Makefile команды

```bash
# Установка зависимостей
make install          # Продакшн зависимости
make install-dev      # С dev зависимостями

# Качество кода
make format           # Форматирование (Ruff + Black)
make lint            # Линтинг (Ruff + MyPy + Bandit)  
make security        # Проверка безопасности
make check           # Полная проверка

# Тестирование
make test            # Запуск тестов
make test-cov        # Тесты с покрытием
make test-watch      # Continuous testing

# Запуск приложения
make dev             # Development mode
make run             # Production mode

# Docker
make docker-dev      # Development в Docker
make docker-build    # Сборка образа

# Очистка
make clean           # Временные файлы
```

### uv команды

```bash
# Синхронизация зависимостей
uv sync

# Добавление новых зависимостей
uv add fastapi
uv add --dev pytest

# Обновление зависимостей  
uv lock --upgrade

# Запуск команд в виртуальном окружении
uv run python script.py
uv run uvicorn main:app --reload
uv run pytest
```

## Архитектурные принципы

### Clean Architecture

```python
# ✅ ПРАВИЛЬНО - Чистое разделение слоев
class ConversationController(BaseController):
    def __init__(self, conversation_service: ConversationService):
        self.conversation_service = conversation_service
    
    async def process_chat_message(self, request: ChatRequest) -> ChatResponse:
        # Только HTTP валидация и делегирование
        validated_request = self._validate_request(request)
        result = await self.conversation_service.process_conversation(
            user_id=validated_request.user_id,
            message=validated_request.message
        )
        return self._format_response(result)

# ❌ НЕПРАВИЛЬНО - Смешивание слоев  
class ConversationController:
    async def process_chat_message(self, request):
        # Прямой доступ к репозиторию - нарушение архитектуры!
        user = await user_repository.get_by_id(request.user_id)
        
        # Бизнес-логика в контроллере - неправильно!
        if user.subscription_expired():
            return {"error": "Subscription expired"}
            
        # Прямой вызов внешнего API - нарушение!
        ai_response = await openai.chat.completions.create(...)
```

### Dependency Injection

```python
# app/api/dependencies.py
def get_conversation_service() -> ConversationService:
    return ConversationService(
        conversation_repository=get_conversation_repository(),
        nlp_service=get_nlp_service(),
        ai_service=get_ai_service(),
    )

def get_conversation_repository() -> ConversationRepository:
    if settings.database_type == "postgresql":
        return SQLAlchemyConversationRepository(
            session_factory=get_database_session
        )
    elif settings.database_type == "memory":
        return InMemoryConversationRepository()
```

### Repository Pattern

```python
# Абстракция
class ConversationRepository(ABC):
    @abstractmethod
    async def get_session_history(
        self, session_id: str, limit: int = 50
    ) -> list[Message]:
        pass

# Реализация
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

## Правила написания кода

### Контроллеры

**Принципы:**
- Только HTTP логика
- Максимум 50 строк на метод
- Делегирование бизнес-логики сервисам
- Стандартная обработка ошибок через BaseController

```python
class MessagingController(BaseController):
    def __init__(self, messaging_service: MessagingService):
        super().__init__()
        self.messaging_service = messaging_service

    async def send_message(self, request: SendMessageRequest) -> SendMessageResponse:
        return await self.handle_request(
            self._send_message_impl,
            request
        )

    async def _send_message_impl(self, request: SendMessageRequest) -> SendMessageResponse:
        # HTTP валидация
        validated_request = self._validate_send_message_request(request)
        
        # Создание доменной модели
        message = UnifiedMessage(
            message_id=str(uuid.uuid4()),
            platform=validated_request.platform,
            chat_id=validated_request.chat_id,
            text=validated_request.text
        )
        
        # Делегирование сервису
        result = await self.messaging_service.send_message(
            platform=validated_request.platform,
            chat_id=validated_request.chat_id,
            message=message
        )
        
        # HTTP форматирование
        return SendMessageResponse(
            success=result.success,
            message_id=result.message_id
        )
```

### Сервисы

**Принципы:**
- Вся бизнес-логика здесь
- Взаимодействие с репозиториями и адаптерами
- Доменная валидация
- Структурированное логирование

```python
class ConversationService:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        nlp_service: NLPService,
        ai_service: AIService,
    ):
        self.conversation_repository = conversation_repository
        self.nlp_service = nlp_service
        self.ai_service = ai_service
        self.logger = structlog.get_logger()

    async def process_conversation(
        self, user_id: str, session_id: str, message: str
    ) -> ConversationResult:
        # Доменная валидация
        if not user_id:
            raise ValueError("User ID обязателен")
        if not message.strip():
            raise ValueError("Сообщение не может быть пустым")

        # Получение контекста
        context = await self.conversation_repository.get_context(session_id)
        
        # NLP анализ
        nlp_result = await self.nlp_service.analyze_message(
            message, context.language_code
        )
        
        self.logger.info(
            "Message analyzed",
            user_id=user_id,
            session_id=session_id,
            intent=nlp_result.intent,
            confidence=nlp_result.confidence
        )
        
        # AI генерация ответа
        ai_response = await self.ai_service.generate_response(
            message=message,
            context=context,
            intent=nlp_result.intent
        )
        
        # Сохранение диалога
        await self._save_conversation(
            user_id, session_id, message, ai_response, nlp_result
        )
        
        return ConversationResult(
            response=ai_response.content,
            intent=nlp_result.intent,
            confidence=nlp_result.confidence,
            requires_human=nlp_result.confidence < 0.7
        )
```

### Модели данных

```python
# Domain Models (Pydantic)
class UnifiedMessage(BaseModel):
    message_id: str = Field(..., description="Уникальный ID сообщения")
    platform: str = Field(..., description="Платформа отправки")
    user_id: str = Field(..., description="ID пользователя")
    chat_id: str = Field(..., description="ID чата")
    text: str | None = Field(None, description="Текст сообщения")
    message_type: MessageType = Field(
        default=MessageType.TEXT,
        description="Тип сообщения"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Время создания"
    )

    class Config:
        use_enum_values = True
        validate_assignment = True

# Database Models (SQLAlchemy)  
class MessageModel(Base):
    __tablename__ = "messages"
    
    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid4)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[UUID] = mapped_column(UUID, ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=func.now()
    )
    
    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="messages")
```

## Тестирование

### Структура тестов

```
tests/
├── conftest.py              # Pytest конфигурация и фикстуры
├── unit/                    # Юнит-тесты
│   ├── controllers/
│   ├── services/
│   ├── repositories/
│   └── adapters/
├── integration/             # Интеграционные тесты
│   ├── test_api_endpoints.py
│   ├── test_database.py
│   └── test_external_apis.py
└── e2e/                     # End-to-end тесты
    ├── test_chat_flow.py
    └── test_messaging_flow.py
```

### Фикстуры (conftest.py)

```python
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.database import Base
from app.api.main import app

@pytest.fixture(scope="session")
def settings():
    return get_settings()

@pytest.fixture(scope="session")
async def test_engine(settings):
    engine = create_async_engine(settings.test_database_url)
    
    # Создание таблиц
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Очистка
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
async def db_session(test_engine):
    Session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with Session() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def mock_openai_response():
    return {
        "choices": [
            {
                "message": {
                    "content": "Тестовый ответ от AI",
                    "role": "assistant"
                }
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15
        }
    }
```

### Тестирование контроллеров

```python
# tests/unit/controllers/test_messaging_controller.py
import pytest
from unittest.mock import Mock, AsyncMock

from app.api.controllers.messaging_controller import MessagingController
from app.services.messaging_service import MessagingService
from app.models.messaging import SendMessageRequest, DeliveryResult

class TestMessagingController:
    @pytest.fixture
    def mock_messaging_service(self):
        service = Mock(spec=MessagingService)
        service.send_message = AsyncMock(return_value=DeliveryResult(
            message_id="test_msg_123",
            platform="telegram",
            success=True,
            status="sent"
        ))
        return service
    
    @pytest.fixture  
    def controller(self, mock_messaging_service):
        return MessagingController(messaging_service=mock_messaging_service)
    
    async def test_send_message_success(self, controller, mock_messaging_service):
        # Arrange
        request = SendMessageRequest(
            platform="telegram",
            chat_id="123456789",
            text="Test message"
        )
        
        # Act
        response = await controller.send_message(request)
        
        # Assert
        assert response.success is True
        assert response.message_id == "test_msg_123"
        mock_messaging_service.send_message.assert_called_once()
    
    async def test_send_message_validation_error(self, controller):
        # Arrange
        request = SendMessageRequest(
            platform="",  # Пустая платформа
            chat_id="123456789",
            text="Test message"
        )
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await controller.send_message(request)
        
        assert exc_info.value.status_code == 400
        assert "Platform name is required" in str(exc_info.value.detail)
```

### Тестирование сервисов

```python
# tests/unit/services/test_conversation_service.py
import pytest
from unittest.mock import Mock, AsyncMock

from app.services.conversation_service import ConversationService
from app.models.conversation import ConversationResult

class TestConversationService:
    @pytest.fixture
    def mock_conversation_repository(self):
        repo = Mock()
        repo.get_context = AsyncMock(return_value=Mock(
            session_id="test_session",
            language_code="ru"
        ))
        repo.save_message = AsyncMock()
        return repo
    
    @pytest.fixture
    def mock_nlp_service(self):
        service = Mock()
        service.analyze_message = AsyncMock(return_value=Mock(
            intent="greeting",
            confidence=0.95
        ))
        return service
    
    @pytest.fixture  
    def service(self, mock_conversation_repository, mock_nlp_service, mock_ai_service):
        return ConversationService(
            conversation_repository=mock_conversation_repository,
            nlp_service=mock_nlp_service,
            ai_service=mock_ai_service
        )
    
    async def test_process_conversation_success(self, service):
        # Act
        result = await service.process_conversation(
            user_id="user_123",
            session_id="session_456",
            message="Привет!"
        )
        
        # Assert
        assert isinstance(result, ConversationResult)
        assert result.intent == "greeting"
        assert result.confidence == 0.95
        assert result.response is not None
    
    async def test_process_conversation_empty_message(self, service):
        # Act & Assert
        with pytest.raises(ValueError, match="Сообщение не может быть пустым"):
            await service.process_conversation(
                user_id="user_123",
                session_id="session_456", 
                message=""
            )
```

### Интеграционные тесты

```python
# tests/integration/test_api_endpoints.py
import pytest
from httpx import AsyncClient

class TestConversationAPI:
    async def test_chat_endpoint_success(self, client: AsyncClient):
        # Arrange
        payload = {
            "message": "Привет!",
            "user_id": "test_user_123",
            "platform": "web"
        }
        
        # Act
        response = await client.post("/api/v1/conversation/chat", json=payload)
        
        # Assert
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "session_id" in data
        assert "intent" in data
        assert data["intent"] is not None
    
    async def test_chat_endpoint_validation_error(self, client: AsyncClient):
        # Arrange - отсутствует обязательное поле user_id
        payload = {
            "message": "Привет!",
            "platform": "web"
        }
        
        # Act
        response = await client.post("/api/v1/conversation/chat", json=payload)
        
        # Assert
        assert response.status_code == 422
```

### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием кода
pytest --cov=app tests/

# Только юнит-тесты
pytest tests/unit/

# Конкретный файл
pytest tests/unit/services/test_conversation_service.py

# Конкретный тест
pytest tests/unit/services/test_conversation_service.py::TestConversationService::test_process_conversation_success

# В verbose режиме
pytest -v

# Остановка при первой ошибке
pytest -x

# Continuous testing (запуск при изменениях)
pytest-watch
```

## Логирование

### Структурированное логирование

```python
import structlog

# Настройка логирования
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Использование в коде
logger = structlog.get_logger()

# В сервисах
logger.info(
    "Processing conversation",
    user_id=user_id,
    session_id=session_id,
    intent=intent,
    confidence=confidence
)

# Ошибки
logger.error(
    "External API call failed",
    platform="wildberries",
    error=str(error),
    retry_count=retry_count
)

# В контроллерах (только критические ошибки)
logger.error(
    "Unexpected controller error",
    controller=self.__class__.__name__,
    endpoint=request.url.path,
    error=str(error)
)
```

## Качество кода

### Pre-commit hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ["-r", "app/"]

  - repo: https://github.com/psf/black
    rev: 23.11.0
    hooks:
      - id: black
```

### Установка и использование

```bash
# Установка
pre-commit install

# Запуск на всех файлах
pre-commit run --all-files

# Автоматический запуск при коммите
git add .
git commit -m "Add new feature"  # pre-commit выполнится автоматически
```

## Отладка

### VS Code настройка

```json
// .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "FastAPI Development",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/.venv/bin/uvicorn",
            "args": [
                "main:app",
                "--reload",
                "--host", "0.0.0.0",
                "--port", "8000"
            ],
            "console": "integratedTerminal",
            "envFile": "${workspaceFolder}/.env"
        },
        {
            "name": "Debug Tests",
            "type": "python", 
            "request": "launch",
            "module": "pytest",
            "args": ["${file}"],
            "console": "integratedTerminal",
            "envFile": "${workspaceFolder}/.env"
        }
    ]
}
```

### Профилирование производительности

```python
import cProfile
import pstats
from functools import wraps

def profile_performance(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        
        result = await func(*args, **kwargs)
        
        pr.disable()
        stats = pstats.Stats(pr)
        stats.sort_stats('cumulative')
        stats.print_stats(20)  # Топ 20 функций
        
        return result
    return wrapper

# Использование
@profile_performance
async def slow_function():
    # Код для профилирования
    pass
```

---

🤖 Создано с помощью [Claude Code](https://claude.ai/code)