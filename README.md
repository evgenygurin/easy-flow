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

- **Backend**: FastAPI, Python 3.11+
- **AI/ML**: OpenAI GPT, YandexGPT, LangChain
- **База данных**: PostgreSQL, Redis
- **Архитектура**: Микросервисы, REST API
- **Деплой**: Docker, Kubernetes ready

## 📋 Быстрый старт

### Предварительные требования

- Python 3.11+
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

4. **Или локально**

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
WHATSAPP_ACCESS_TOKEN=your-whatsapp-token

# Платежи
YOOKASSA_SHOP_ID=your-shop-id
YOOKASSA_SECRET_KEY=your-secret-key
```

## 📚 API Документация

### Основные endpoints

#### Чат с AI

```http
POST /api/v1/conversation/chat
Content-Type: application/json

{
  "message": "Где мой заказ №12345?",
  "user_id": "user123",
  "platform": "web"
}
```

#### Управление интеграциями

```http
GET /api/v1/integration/platforms
GET /api/v1/integration/connected?user_id=user123
POST /api/v1/integration/connect
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

#### Мессенджеры

- **Telegram** - популярный мессенджер
- **WhatsApp Business** - бизнес мессенджер
- **VK** - российская соцсеть
- **Viber** - мессенджер с бизнес функциями

#### Голосовые ассистенты

- **Yandex Alice** - российский голосовой помощник
- **Amazon Alexa** - международный стандарт
- **Google Assistant** - Google экосистема
- **Apple Siri** - iOS интеграция

## 🏗️ Архитектура

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
