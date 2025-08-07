# AI Customer Support Platform

Универсальная AI платформа для поддержки клиентов в e-commerce с фокусом на российский рынок и возможностью глобального расширения.

## 🚀 Особенности

### Основные возможности

- **AI Чат-бот** - умный помощник с поддержкой русского языка
- **Голосовые ассистенты** - интеграция с Yandex Alice, Alexa, Google Assistant
- **Омниканальность** - единый интерфейс для всех каналов связи
- **E-commerce интеграции** - Wildberries, Ozon, 1C-Bitrix, Shopify
- **Мессенджеры** - Telegram, WhatsApp, VK, Viber
- **Аналитика** - отчеты и метрики производительности

### Технологический стек

- **Backend**: FastAPI, Python 3.12+
- **AI/ML**: OpenAI GPT, YandexGPT, LangChain
- **База данных**: PostgreSQL, Redis
- **Архитектура**: Микросервисы, REST API
- **Деплой**: Docker, Kubernetes ready

## 📋 Быстрый старт

### Предварительные требования

- Python 3.12+
- Docker и Docker Compose
- PostgreSQL 15+
- Redis 7+

### Установка

1. **Клонируйте репозиторий**

```bash
git clone https://github.com/evgenygurin/easy-flow.git
cd easy-flow
```

2. **Настройте окружение**

```bash
cp .env.example .env
# Отредактируйте .env файл с вашими API ключами
```

3. **Запустите с Docker Compose**

```bash
docker-compose up -d
```

4. **Или локально (с uv)**

```bash
# Установите uv (если еще не установлен)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Установите зависимости и запустите
uv sync
uv run uvicorn main:app --reload
```

**Альтернатива с pip:**

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

### Первоначальная настройка

API будет доступно по адресу: <http://localhost:8000>

- **Документация API**: <http://localhost:8000/docs>
- **ReDoc**: <http://localhost:8000/redoc>  
- **Health Check**: <http://localhost:8000/health/>

## 🔧 Конфигурация

### Основные переменные окружения

```bash
# AI сервисы
OPENAI_API_KEY=sk-your-openai-api-key
YANDEX_GPT_API_KEY=your-yandex-gpt-key

# E-commerce платформы
WILDBERRIES_API_KEY=your-wb-api-key
OZON_API_KEY=your-ozon-api-key

# Мессенджеры
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_WEBHOOK_SECRET=your-webhook-secret

WHATSAPP_ACCESS_TOKEN=your-whatsapp-token
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id
WHATSAPP_WEBHOOK_VERIFY_TOKEN=your-verify-token

VK_ACCESS_TOKEN=your-vk-access-token
VK_GROUP_ID=your-group-id
VK_SECRET_KEY=your-secret-key

VIBER_AUTH_TOKEN=your-viber-auth-token

# Платежи
YOOKASSA_SHOP_ID=your-shop-id
YOOKASSA_SECRET_KEY=your-secret-key
```

## ⚡ Команды разработки

Проект использует **uv** для управления зависимостями и **Make** для автоматизации задач.

### Установка и настройка

```bash
# Установка всех зависимостей
make install

# Установка с dev-зависимостями
make install-dev
```

### Качество кода

```bash
# Форматирование кода
make format

# Проверка линтерами
make lint

# Проверка безопасности
make security

# Полная проверка (форматирование + линтинг + безопасность + тесты)
make check
```

### Тестирование

```bash
# Запуск тестов
make test

# Тесты с покрытием
make test-cov

# Pre-commit хуки
make pre-commit
```

### Запуск приложения

```bash
# Производственный режим
make run

# Режим разработки
make dev

# Docker
make docker-dev
```

### Очистка

```bash
# Очистить временные файлы
make clean
```

### Команды uv напрямую

```bash
# Синхронизация зависимостей
uv sync

# Добавить зависимость
uv add fastapi

# Запуск команды в виртуальном окружении
uv run python script.py

# Обновить зависимости
uv lock --upgrade
```

## 📚 API Документация

### ✨ Новая Clean Controller Architecture

API теперь использует чистую архитектуру контроллеров:

```python
# До: Бизнес-логика в маршрутах ❌
@router.post("/chat")
async def process_chat_message(request, service1, service2):
    # 150+ строк бизнес-логики в маршруте
    session_id = request.session_id or str(uuid.uuid4())
    nlp_result = await nlp_service.process_message(...)
    # ... сложная логика

# После: Тонкий слой маршрутов ✅  
@router.post("/chat")
async def process_chat_message(
    request: ChatRequest,
    controller: ConversationController = Depends()
) -> ChatResponse:
    return await controller.process_chat_message(request)
```

### Основные endpoints

#### Чат с AI

```http
POST /api/v1/conversation/chat
Content-Type: application/json

{
  "message": "Где мой заказ №12345?",
  "user_id": "user123", 
  "session_id": "optional-session-id",
  "platform": "web",
  "context": {}
}
```

**Ответ:**
```json
{
  "message": "Ваш заказ №12345 находится в доставке...",
  "session_id": "generated-or-provided-id",
  "intent": "order_status",
  "entities": {"order_id": "12345"},
  "confidence": 0.95,
  "requires_human": false,
  "current_state": "order_inquiry"
}
```

#### Управление интеграциями

```http
GET /api/v1/integration/platforms
GET /api/v1/integration/connected?user_id=user123
POST /api/v1/integration/connect
DELETE /api/v1/integration/disconnect/{platform_id}
```

#### Синхронизация данных

```http
POST /api/v1/integration/sync/{platform_id}
POST /api/v1/integration/sync-all
```

#### Webhook'и

```http
POST /api/v1/integration/webhook/{platform}
```

### Поддерживаемые платформы

#### E-commerce

- **Wildberries** - российский маркетплейс
- **Ozon** - российская e-commerce платформа  
- **1C-Bitrix** - CRM и e-commerce решение
- **InSales** - платформа для интернет-магазинов
- **Shopify** - международная платформа
- **WooCommerce** - WordPress e-commerce

#### 📱 Интеграция с мессенджерами

Платформа поддерживает полную интеграцию с популярными мессенджерами:

##### Поддерживаемые платформы

- **Telegram Bot API** - полная поддержка inline и reply клавиатур, медиа, файлов
- **WhatsApp Business Cloud API** - сообщения, медиа, шаблоны, интерактивные кнопки
- **VK Bot API** - сообщения, клавиатуры, карусели, вложения
- **Viber Business API** - богатые медиа, клавиатуры, широкие возможности

##### API Endpoints для мессенджеров

```http
# Отправка сообщений
POST /api/v1/messaging/send
{
  "platform": "telegram",
  "chat_id": "123456789",
  "text": "Ваш заказ готов к получению!",
  "message_type": "text",
  "inline_keyboard": {
    "buttons": [[{"text": "Отследить", "callback_data": "track_order"}]]
  },
  "priority": 5
}

# Обработка webhook'ов
POST /api/v1/messaging/webhook/{platform}
# Автоматическая обработка входящих сообщений

# Получение контекста диалога
GET /api/v1/messaging/context/{platform}/{chat_id}/{user_id}

# Обновление контекста диалога
PUT /api/v1/messaging/context/{platform}/{chat_id}/{user_id}

# Статистика платформы
GET /api/v1/messaging/stats/{platform}

# Список поддерживаемых платформ
GET /api/v1/messaging/platforms
```

##### Конфигурация мессенджеров

```bash
# Telegram Bot API
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_WEBHOOK_SECRET=your-secret-token
TELEGRAM_WEBHOOK_URL=https://your-domain.com/api/v1/messaging/webhook/telegram

# WhatsApp Business Cloud API  
WHATSAPP_ACCESS_TOKEN=your-whatsapp-access-token
WHATSAPP_WEBHOOK_VERIFY_TOKEN=your-verify-token
WHATSAPP_WEBHOOK_SECRET=your-webhook-secret
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id

# VK Bot API
VK_ACCESS_TOKEN=your-vk-access-token
VK_GROUP_ID=your-group-id
VK_SECRET_KEY=your-secret-key
VK_CONFIRMATION_TOKEN=your-confirmation-token

# Viber Bot API
VIBER_AUTH_TOKEN=your-viber-auth-token
VIBER_WEBHOOK_URL=https://your-domain.com/api/v1/messaging/webhook/viber
```

##### Примеры использования

**Telegram интеграция:**

```python
# Отправка сообщения с inline клавиатурой
await messaging_service.send_message(
    platform="telegram",
    chat_id="123456789",
    message=UnifiedMessage(
        text="Выберите действие:",
        message_type=MessageType.TEXT,
        inline_keyboard=InlineKeyboard(
            buttons=[
                [InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders")],
                [InlineKeyboardButton(text="🛒 Каталог", callback_data="catalog")],
                [InlineKeyboardButton(text="🔍 Поиск", callback_data="search")]
            ]
        )
    ),
    priority=5
)
```

**WhatsApp интеграция:**

```python
# Отправка медиа сообщения
await messaging_service.send_message(
    platform="whatsapp",
    chat_id="71234567890",
    message=UnifiedMessage(
        text="Ваш QR-код для получения заказа:",
        message_type=MessageType.IMAGE,
        attachments=[
            MessageAttachment(
                file_type="image",
                file_url="https://api.qrserver.com/v1/create-qr-code/?data=ORDER123",
                file_name="qr_code.png"
            )
        ]
    )
)
```

**Универсальная обработка webhook'ов:**

```python
@app.post("/api/v1/messaging/webhook/{platform}")
async def process_webhook(platform: str, request: Request):
    # Автоматическая обработка входящих сообщений
    # Поддержка всех платформ через единый интерфейс
    payload = await request.json()
    
    # Извлечение и нормализация сообщений
    messages = await messaging_service.process_webhook(
        platform=platform,
        payload=payload,
        signature=request.headers.get("x-signature")
    )
    
    # Обработка через AI и генерация ответов
    for message in messages:
        response = await conversation_service.process_message(message)
        await messaging_service.send_message(
            platform=platform,
            chat_id=message.chat_id,
            message=response
        )
```

##### Возможности мессенджеров

| Функция | Telegram | WhatsApp | VK | Viber |
|---------|----------|----------|----| ------|
| Текстовые сообщения | ✅ | ✅ | ✅ | ✅ |
| Inline клавиатуры | ✅ | ✅ | ✅ | ✅ |
| Reply клавиатуры | ✅ | ❌ | ✅ | ✅ |
| Изображения | ✅ | ✅ | ✅ | ✅ |
| Видео | ✅ | ✅ | ✅ | ✅ |
| Документы | ✅ | ✅ | ✅ | ✅ |
| Голосовые сообщения | ✅ | ✅ | ✅ | ❌ |
| Стикеры | ✅ | ✅ | ✅ | ✅ |
| Карусели | ❌ | ✅ | ✅ | ✅ |
| Шаблоны | ❌ | ✅ | ❌ | ✅ |
| Групповые чаты | ✅ | ✅ | ✅ | ❌ |
| Webhook'и | ✅ | ✅ | ✅ | ✅ |

##### Автоматизация и интеллект

- **Автоматическая обработка** входящих сообщений
- **NLP анализ** намерений и сущностей в сообщениях
- **Контекстные ответы** на основе истории диалога
- **Интеграция с AI** для генерации персонализированных ответов
- **Эскалация** сложных вопросов к операторам
- **Аналитика** эффективности каналов связи

#### Голосовые ассистенты

- **Yandex Alice** - российский голосовой помощник
- **Amazon Alexa** - международный стандарт
- **Google Assistant** - Google экосистема
- **Apple Siri** - iOS интеграция

## 🏗️ Архитектура

Проект следует принципам **Clean Architecture** с четким разделением слоев:

### Clean Architecture Layers

```
app/
├── api/                    # 🌐 Presentation Layer
│   ├── controllers/        # HTTP логика (новое!)
│   ├── routes/            # Тонкие FastAPI маршруты
│   └── dependencies.py    # Dependency Injection
├── services/              # 💼 Business Logic Layer  
│   ├── conversation_service.py
│   ├── integration_service.py
│   ├── nlp_service.py
│   └── ai_service.py
├── repositories/          # 💾 Data Access Layer
│   ├── interfaces/        # Repository абстракции
│   └── sqlalchemy/       # SQLAlchemy реализации  
├── adapters/              # 🔌 External Integrations
│   ├── russian/          # Российские платформы
│   └── international/    # Международные платформы
└── models/               # 📊 Domain Models
```

### Микросервисы

```
├── Conversation Service    # Управление диалогами
├── NLP Processing Service  # Обработка языка  
├── AI Model Service       # Генерация ответов
├── Integration Service    # Внешние интеграции
├── User Context Service   # Контекст пользователей
├── Analytics Service      # Аналитика и метрики
└── Notification Service   # Уведомления
```

### Схема базы данных

```sql
-- Пользователи и сессии
users, sessions, conversations, messages

-- Интеграции
integrations, platforms, webhooks

-- Аналитика  
metrics, events, reports
```

## 🧪 Тестирование и качество кода

### Настройка инструментов качества кода

Проект использует современные инструменты для поддержания высокого качества кода:

#### Установка pre-commit хуков

```bash
# Установите pre-commit хуки для автоматической проверки
pre-commit install

# Запуск проверки на всех файлах
pre-commit run --all-files
```

#### Инструменты качества кода

**Ruff** - быстрый линтер и форматтер:

```bash
# Проверка и автоматическое исправление
ruff check app/ tests/ --fix

# Форматирование кода
ruff format app/ tests/
```

**Black** - форматирование кода:

```bash
# Форматирование
black app/ tests/

# Проверка без изменений
black --check app/ tests/
```

**MyPy** - проверка типов:

```bash
# Проверка типов
mypy app/ --config-file=pyproject.toml
```

**Bandit** - проверка безопасности:

```bash
# Проверка уязвимостей безопасности
bandit -r app/ --format json
```

**Safety** - проверка зависимостей:

```bash
# Проверка известных уязвимостей в зависимостях
safety check --json
```

### Запуск тестов

```bash
# Запуск всех тестов
pytest

# Запуск с покрытием кода
pytest --cov=app tests/

# Генерация HTML отчета покрытия
pytest --cov=app --cov-report=html tests/
```

### Makefile команды

```bash
# Установка зависимостей
make install

# Запуск всех проверок качества кода
make lint

# Форматирование кода
make format

# Запуск тестов
make test

# Полная проверка (линтинг + тесты)
make check
```

### Настройка IDE

#### VS Code

Рекомендуемые расширения (.vscode/extensions.json):

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.mypy-type-checker",
    "charliermarsh.ruff",
    "ms-python.black-formatter"
  ]
}
```

#### PyCharm

1. Установите плагин Ruff
2. Настройте Black как форматтер кода
3. Включите проверку типов MyPy

### CI/CD Pipeline

Проект автоматически проверяется в GitHub Actions:

- ✅ Линтинг с Ruff
- ✅ Форматирование с Black
- ✅ Проверка типов с MyPy  
- ✅ Проверка безопасности с Bandit
- ✅ Проверка уязвимостей с Safety
- ✅ Запуск тестов с покрытием кода

## 📊 Мониторинг и аналитика

### Метрики

- Время ответа AI
- Точность распознавания намерений
- Количество эскалаций к операторам
- Удовлетворенность клиентов

### Логирование

```python
import structlog
logger = structlog.get_logger()
logger.info("Обработка сообщения", user_id=user_id, intent=intent)
```

## 🚀 Деплой

### Docker

```bash
docker build -t ai-support .
docker run -p 8000:8000 ai-support
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-support
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: ai-support
        image: ai-support:latest
        ports:
        - containerPort: 8000
```

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте feature ветку (`git checkout -b feature/amazing-feature`)
3. Зафиксируйте изменения (`git commit -m 'Add amazing feature'`)
4. Запушьте в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📄 Лицензия

Проект распространяется под лицензией MIT. См. файл [LICENSE](LICENSE) для подробностей.

## 📞 Поддержка

- **Issues**: [GitHub Issues](https://github.com/evgenygurin/easy-flow/issues)
- **Email**: <support@ai-platform.ru>
- **Telegram**: @ai_support_bot

## 🗺️ Roadmap

### MVP (0-6 месяцев)

- [x] Базовая архитектура FastAPI
- [x] Интеграция с OpenAI/YandexGPT
- [x] Поддержка Telegram и WhatsApp
- [x] Интеграция с Wildberries и Ozon
- [x] **Clean Controller Architecture** ✨
- [x] Repository Pattern с интерфейсами
- [x] Dependency Injection система
- [ ] Веб-интерфейс для управления
- [ ] Базовая аналитика

### Рост (6-18 месяцев)  

- [ ] Голосовые ассистенты (Alice, Alexa)
- [ ] Дополнительные платформы (Shopify, WooCommerce)
- [ ] Расширенная аналитика и BI
- [ ] Мобильные приложения
- [ ] Белый лейбл

### Масштаб (18+ месяцев)

- [ ] Международное расширение  
- [ ] AR/VR интеграции
- [ ] Blockchain и Web3 поддержка
- [ ] Собственные ML модели
- [ ] Enterprise функции

---

🤖 **Создано с помощью [Claude Code](https://claude.ai/code)**
