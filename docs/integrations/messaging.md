# 💬 Мессенджеры

## Поддерживаемые платформы

### Telegram
Популярный мессенджер с богатыми возможностями для ботов

**Настройка:**
```bash
TELEGRAM_BOT_TOKEN=your-bot-token
```

**Возможности:**
- Текстовые сообщения
- Inline клавиатуры
- Отправка файлов и медиа
- Группы и каналы
- Webhook'и для мгновенной доставки

**Создание бота:**
1. Напишите @BotFather в Telegram
2. Создайте нового бота командой `/newbot`
3. Получите токен и добавьте в конфигурацию

### WhatsApp Business
Официальное API для бизнеса

**Настройка:**
```bash
WHATSAPP_ACCESS_TOKEN=your-whatsapp-token
WHATSAPP_PHONE_NUMBER_ID=your-phone-id
```

**Возможности:**
- Сообщения и медиа
- Шаблоны сообщений
- Интерактивные кнопки
- Статусы доставки
- Групповые чаты

### VK (ВКонтакте)
Российская социальная сеть

**Настройка:**
```bash
VK_ACCESS_TOKEN=your-vk-token
VK_GROUP_ID=your-group-id
```

**Возможности:**
- Сообщения сообщества
- Комментарии к постам
- Личные сообщения
- Интеграция с VK Mini Apps

### Viber
Мессенджер с бизнес функциями

**Настройка:**
```bash
VIBER_ACCESS_TOKEN=your-viber-token
```

**Возможности:**
- Rich media сообщения
- Клавиатуры и карусели
- Широковещательные сообщения
- Аналитика сообщений

## Универсальные webhook'и

### Получение сообщений
```http
POST /api/v1/integration/webhook/telegram
POST /api/v1/integration/webhook/whatsapp
POST /api/v1/integration/webhook/vk
POST /api/v1/integration/webhook/viber
```

### Отправка сообщений
```http
POST /api/v1/conversation/send
Content-Type: application/json

{
  "platform": "telegram",
  "user_id": "123456789",
  "message": "Привет! Как дела?",
  "type": "text"
}
```

## Типы сообщений

### Текстовые
```json
{
  "type": "text",
  "content": "Ваш заказ готов к получению!"
}
```

### С кнопками
```json
{
  "type": "interactive",
  "content": "Выберите действие:",
  "buttons": [
    {"text": "Отследить заказ", "callback": "track_order"},
    {"text": "Связаться с поддержкой", "callback": "contact_support"}
  ]
}
```

### Медиа
```json
{
  "type": "media",
  "media_type": "image",
  "url": "https://example.com/image.jpg",
  "caption": "Ваш заказ упакован"
}
```

## Настройка автоответов

Для каждого мессенджера можно настроить:
- Приветственные сообщения
- Меню быстрых ответов
- Автоматические уведомления
- Эскалация к операторам

## Аналитика

Отслеживание метрик:
- Количество сообщений
- Время ответа
- Конверсия диалогов
- Удовлетворенность клиентов