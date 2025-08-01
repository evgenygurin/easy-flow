# Easy Flow - AI Customer Support Platform

Универсальная AI платформа для поддержки клиентов в e-commerce с фокусом на российский рынок и возможностью глобального расширения.

## ✨ Основные возможности

- 🤖 **AI Чат-бот** - умный помощник с поддержкой русского языка
- 🎙️ **Голосовые ассистенты** - интеграция с Yandex Alice, Alexa, Google Assistant
- 🌐 **Омниканальность** - единый интерфейс для всех каналов связи
- 🛒 **E-commerce интеграции** - Wildberries, Ozon, 1C-Bitrix, Shopify
- 💬 **Мессенджеры** - Telegram, WhatsApp, VK, Viber
- 📊 **Аналитика** - отчеты и метрики производительности

## 🛠️ Технологический стек

- **Backend**: FastAPI, Python 3.11+
- **AI/ML**: OpenAI GPT, YandexGPT, LangChain
- **База данных**: PostgreSQL, Redis
- **Архитектура**: Микросервисы, REST API
- **Деплой**: Docker, Kubernetes ready

## 🚀 Быстрый старт

### Установка и запуск

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/evgenygurin/easy-flow.git
cd easy-flow

# 2. Запустите с Docker Compose
docker-compose up -d

# 3. Или локально
pip install -r requirements.txt
uvicorn main:app --reload
```

**API доступно по адресу**: http://localhost:8000
- 📖 [Документация API](http://localhost:8000/docs)
- 🔍 [Health Check](http://localhost:8000/health/)

Подробная инструкция: [📋 Руководство по установке](docs/quickstart.md)

## 📚 Документация

Полная документация проекта доступна в папке [`docs/`](docs/):

### 📖 Основные разделы
- **[🚀 Быстрый старт](docs/quickstart.md)** - Установка и первоначальная настройка
- **[🔧 Конфигурация](docs/configuration.md)** - Настройка переменных окружения
- **[📚 API Документация](docs/api.md)** - Полное описание REST API
- **[🏗️ Архитектура](docs/architecture.md)** - Описание системной архитектуры

### 🔌 Интеграции
- **[🛒 E-commerce](docs/integrations/ecommerce.md)** - Wildberries, Ozon, Shopify
- **[💬 Мессенджеры](docs/integrations/messaging.md)** - Telegram, WhatsApp, VK
- **[🎙️ Голосовые ассистенты](docs/integrations/voice.md)** - Alice, Alexa, Google Assistant

### 🛠️ Разработка
- **[🧪 Тестирование](docs/testing.md)** - Инструменты качества кода и тестирования
- **[🚀 Деплой](docs/deployment.md)** - Развертывание в production
- **[🔐 Безопасность](docs/security.md)** - Руководство по безопасности
- **[📊 Мониторинг](docs/monitoring.md)** - Метрики и аналитика

### 🤝 Участие
- **[🤝 Вклад в проект](docs/contributing.md)** - Как участвовать в разработке
- **[🗺️ Roadmap](docs/roadmap.md)** - Планы развития проекта

## 📞 Поддержка

- **Issues**: [GitHub Issues](https://github.com/evgenygurin/easy-flow/issues)
- **Email**: support@ai-platform.ru  
- **Telegram**: @ai_support_bot

## 📄 Лицензия

Проект распространяется под лицензией MIT. См. файл [LICENSE](LICENSE) для подробностей.

---

🤖 **Создано с помощью [Claude Code](https://claude.ai/code)**