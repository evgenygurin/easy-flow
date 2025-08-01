# 🔧 Конфигурация

## Основные переменные окружения

### AI сервисы
```bash
OPENAI_API_KEY=sk-your-openai-api-key
YANDEX_GPT_API_KEY=your-yandex-gpt-key
```

### E-commerce платформы
```bash
WILDBERRIES_API_KEY=your-wb-api-key
OZON_API_KEY=your-ozon-api-key
```

### Мессенджеры
```bash
TELEGRAM_BOT_TOKEN=your-bot-token
WHATSAPP_ACCESS_TOKEN=your-whatsapp-token
```

### Платежи
```bash
YOOKASSA_SHOP_ID=your-shop-id
YOOKASSA_SECRET_KEY=your-secret-key
```

## Файл конфигурации

Создайте файл `.env` на основе `.env.example` и заполните необходимые переменные окружения.

### Пример .env файла
```bash
# Базовые настройки
DEBUG=true
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/easy_flow

# AI провайдеры
OPENAI_API_KEY=sk-your-openai-key
YANDEX_GPT_API_KEY=your-yandex-key

# Интеграции
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
WILDBERRIES_API_KEY=your-wb-key
OZON_API_KEY=your-ozon-key

# Кэширование
REDIS_URL=redis://localhost:6379/0
```

## Настройка интеграций

Подробную информацию о настройке конкретных интеграций см. в разделе [Интеграции](integrations/).