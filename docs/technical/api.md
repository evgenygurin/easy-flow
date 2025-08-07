# 📡 API Документация Easy Flow

## Обзор API

Easy Flow предоставляет RESTful API для интеграции с системой управления диалогами и автоматизации поддержки клиентов.

**Base URL**: `https://api.easyflow.dev/api/v1`  
**Локальная разработка**: `http://localhost:8000/api/v1`

### Документация
- **Interactive Docs**: `/docs` (Swagger UI)
- **ReDoc**: `/redoc` (альтернативный интерфейс)
- **OpenAPI Schema**: `/openapi.json`

## Аутентификация

### API Keys
```http
Authorization: Bearer your-api-key-here
```

### JWT Tokens
```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

## Основные Endpoints

### 💬 Conversation API

#### POST `/conversation/chat`
Обработка сообщения чата с AI ассистентом.

**Request:**
```http
POST /api/v1/conversation/chat
Content-Type: application/json
Authorization: Bearer your-api-key

{
  "message": "Где мой заказ №12345?",
  "user_id": "user_123",
  "session_id": "session_456", // Optional
  "platform": "web",
  "context": {
    "user_name": "Иван Петров",
    "order_history": ["12345", "12344"]
  }
}
```

**Response:**
```json
{
  "message": "Ваш заказ №12345 находится в пути. Ожидаемая дата доставки: 15 января 2024.",
  "session_id": "session_456",
  "intent": "order_status",
  "entities": {
    "order_id": "12345",
    "status": "in_transit"
  },
  "confidence": 0.95,
  "requires_human": false,
  "current_state": "order_inquiry",
  "suggested_actions": [
    {
      "type": "track_order",
      "text": "Отследить заказ",
      "data": {"order_id": "12345"}
    }
  ]
}
```

#### GET `/conversation/sessions/{user_id}`
Получение сессий пользователя.

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "session_456",
      "platform": "web",
      "created_at": "2024-01-10T10:00:00Z",
      "updated_at": "2024-01-10T10:30:00Z",
      "messages_count": 15,
      "status": "active"
    }
  ]
}
```

#### GET `/conversation/history/{session_id}`
История сообщений сессии.

**Parameters:**
- `limit` (int, optional): Количество сообщений (default: 50)
- `offset` (int, optional): Смещение (default: 0)

**Response:**
```json
{
  "messages": [
    {
      "message_id": "msg_123",
      "session_id": "session_456",
      "user_id": "user_123",
      "content": "Где мой заказ №12345?",
      "role": "user",
      "timestamp": "2024-01-10T10:15:00Z",
      "platform": "web"
    },
    {
      "message_id": "msg_124",
      "session_id": "session_456",
      "user_id": "user_123",
      "content": "Ваш заказ находится в пути...",
      "role": "assistant",
      "timestamp": "2024-01-10T10:15:05Z",
      "platform": "web",
      "intent": "order_status",
      "confidence": 0.95
    }
  ],
  "total": 25,
  "has_more": true
}
```

#### POST `/conversation/escalate`
Эскалация к человеку-оператору.

**Request:**
```json
{
  "session_id": "session_456",
  "reason": "complex_issue",
  "priority": "high",
  "context": {
    "issue_type": "payment_problem",
    "user_tier": "premium"
  }
}
```

### 📱 Messaging API

#### POST `/messaging/send`
Отправка сообщения через мессенджер.

**Request:**
```json
{
  "platform": "telegram",
  "chat_id": "123456789",
  "text": "Ваш заказ готов к получению!",
  "message_type": "text",
  "inline_keyboard": {
    "buttons": [
      [
        {
          "text": "📦 Отследить заказ",
          "callback_data": "track_order_12345"
        }
      ],
      [
        {
          "text": "🔄 Изменить адрес",
          "callback_data": "change_address_12345"
        },
        {
          "text": "❌ Отменить заказ", 
          "callback_data": "cancel_order_12345"
        }
      ]
    ]
  },
  "priority": 5
}
```

**Response:**
```json
{
  "success": true,
  "message_id": "msg_internal_789",
  "platform_message_id": "1234",
  "delivery_status": "sent",
  "sent_at": "2024-01-10T10:15:00Z"
}
```

#### POST `/messaging/webhook/{platform}`
Обработка входящих webhook'ов от мессенджеров.

**Telegram Webhook Payload:**
```json
{
  "update_id": 123456,
  "message": {
    "message_id": 1234,
    "from": {
      "id": 123456789,
      "is_bot": false,
      "first_name": "Иван",
      "last_name": "Петров",
      "username": "ivan_petrov"
    },
    "chat": {
      "id": 123456789,
      "first_name": "Иван",
      "last_name": "Петров",
      "username": "ivan_petrov",
      "type": "private"
    },
    "date": 1704794400,
    "text": "Привет! Где мой заказ?"
  }
}
```

#### GET `/messaging/context/{platform}/{chat_id}/{user_id}`
Получение контекста диалога.

**Response:**
```json
{
  "session_id": "session_789",
  "platform": "telegram",
  "chat_id": "123456789",
  "user_id": "123456789",
  "current_state": "waiting_for_order_info",
  "context": {
    "last_order_id": "12345",
    "user_name": "Иван Петров",
    "preferred_language": "ru"
  },
  "created_at": "2024-01-10T09:00:00Z",
  "updated_at": "2024-01-10T10:15:00Z"
}
```

#### PUT `/messaging/context/{platform}/{chat_id}/{user_id}`
Обновление контекста диалога.

#### GET `/messaging/platforms`
Список поддерживаемых платформ.

**Response:**
```json
{
  "platforms": [
    {
      "name": "telegram",
      "display_name": "Telegram",
      "capabilities": ["text", "inline_keyboard", "media", "files", "voice"],
      "webhook_supported": true,
      "status": "active"
    },
    {
      "name": "whatsapp",
      "display_name": "WhatsApp Business",
      "capabilities": ["text", "media", "templates", "interactive_buttons"],
      "webhook_supported": true,
      "status": "active"
    }
  ]
}
```

### 🔌 Integration API

#### GET `/integration/platforms`
Список доступных платформ для интеграции.

**Response:**
```json
{
  "platforms": [
    {
      "id": "wildberries",
      "name": "Wildberries",
      "type": "ecommerce",
      "region": "russia",
      "capabilities": ["orders", "products", "analytics"],
      "required_credentials": ["api_key", "supplier_id"],
      "status": "active"
    },
    {
      "id": "ozon",
      "name": "Ozon",
      "type": "ecommerce", 
      "region": "russia",
      "capabilities": ["orders", "products", "inventory"],
      "required_credentials": ["client_id", "api_key"],
      "status": "active"
    }
  ]
}
```

#### POST `/integration/connect`
Подключение новой платформы.

**Request:**
```json
{
  "user_id": "user_123",
  "platform": "wildberries",
  "credentials": {
    "api_key": "your-wildberries-api-key",
    "supplier_id": "12345"
  },
  "settings": {
    "sync_orders": true,
    "sync_interval": "hourly",
    "webhook_url": "https://your-domain.com/webhooks/wildberries"
  }
}
```

**Response:**
```json
{
  "success": true,
  "connection_id": "conn_456",
  "platform": "wildberries",
  "status": "connected",
  "connected_at": "2024-01-10T10:15:00Z",
  "next_sync": "2024-01-10T11:15:00Z"
}
```

#### GET `/integration/connected`
Получение подключенных платформ пользователя.

**Parameters:**
- `user_id` (string, required)

**Response:**
```json
{
  "connections": [
    {
      "connection_id": "conn_456",
      "platform": "wildberries",
      "status": "connected",
      "connected_at": "2024-01-10T10:15:00Z",
      "last_sync": "2024-01-10T10:15:00Z",
      "sync_status": "success",
      "orders_synced": 1523,
      "products_synced": 89
    }
  ]
}
```

#### POST `/integration/sync/{platform_id}`
Синхронизация данных конкретной платформы.

#### DELETE `/integration/disconnect/{platform_id}`
Отключение платформы.

### 📊 Analytics API

#### GET `/analytics/metrics`
Получение метрик системы.

**Parameters:**
- `start_date` (string, optional): Дата начала (ISO format)
- `end_date` (string, optional): Дата окончания (ISO format)
- `user_id` (string, optional): Фильтр по пользователю

**Response:**
```json
{
  "period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-10T23:59:59Z"
  },
  "conversations": {
    "total": 1523,
    "successful": 1401,
    "escalated": 122,
    "satisfaction_rate": 0.92
  },
  "messages": {
    "total": 15430,
    "inbound": 7832,
    "outbound": 7598,
    "avg_response_time": 1.2
  },
  "platforms": {
    "telegram": {"messages": 8932, "users": 445},
    "whatsapp": {"messages": 4521, "users": 234},
    "web": {"messages": 1977, "users": 128}
  }
}
```

## Модели данных

### ChatRequest
```json
{
  "message": "string",
  "user_id": "string",
  "session_id": "string?",
  "platform": "string",
  "context": "object?"
}
```

### ChatResponse
```json
{
  "message": "string",
  "session_id": "string",
  "intent": "string",
  "entities": "object",
  "confidence": "number",
  "requires_human": "boolean",
  "current_state": "string",
  "suggested_actions": "array?"
}
```

### UnifiedMessage
```json
{
  "message_id": "string",
  "platform": "string",
  "platform_message_id": "string",
  "user_id": "string",
  "chat_id": "string",
  "text": "string?",
  "message_type": "text|image|video|document|voice|sticker",
  "direction": "inbound|outbound",
  "inline_keyboard": "object?",
  "reply_keyboard": "object?",
  "attachments": "array?",
  "timestamp": "string (ISO 8601)",
  "metadata": "object?"
}
```

## Коды ошибок

### HTTP Status Codes
- `200 OK` - Успешный запрос
- `201 Created` - Ресурс создан
- `400 Bad Request` - Неверный запрос
- `401 Unauthorized` - Не авторизован
- `403 Forbidden` - Доступ запрещен
- `404 Not Found` - Ресурс не найден
- `422 Unprocessable Entity` - Ошибка валидации
- `429 Too Many Requests` - Превышен лимит запросов
- `500 Internal Server Error` - Внутренняя ошибка сервера

### Структура ошибок
```json
{
  "error": {
    "type": "validation_error",
    "message": "Invalid request parameters",
    "details": [
      {
        "field": "user_id",
        "error": "This field is required"
      }
    ],
    "request_id": "req_123456"
  }
}
```

## Rate Limiting

### Лимиты по умолчанию
- **Conversation API**: 100 запросов/минута на user_id
- **Messaging API**: 30 сообщений/минута на platform/chat_id
- **Integration API**: 50 запросов/минута на пользователя
- **Analytics API**: 20 запросов/минута на пользователя

### Заголовки ответа
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704794460
```

## Webhook Specifications

### Telegram Webhooks
- **URL**: `/api/v1/messaging/webhook/telegram`
- **Method**: POST
- **Headers**: Автоматическая верификация подписи

### WhatsApp Webhooks
- **URL**: `/api/v1/messaging/webhook/whatsapp`
- **Method**: POST
- **Verification**: GET запрос с verify_token

### VK Webhooks
- **URL**: `/api/v1/messaging/webhook/vk`
- **Method**: POST
- **Verification**: Секретный ключ в payload

## SDK и библиотеки

### Python SDK
```python
from easyflow_sdk import EasyFlowClient

client = EasyFlowClient(api_key="your-api-key")

# Отправка сообщения
response = await client.conversation.chat(
    message="Привет!",
    user_id="user_123"
)

# Отправка в мессенджер
await client.messaging.send(
    platform="telegram",
    chat_id="123456789",
    text="Ваш заказ готов!"
)
```

### JavaScript SDK
```javascript
import { EasyFlowClient } from '@easyflow/sdk';

const client = new EasyFlowClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.easyflow.dev'
});

// Отправка сообщения
const response = await client.conversation.chat({
  message: 'Привет!',
  userId: 'user_123'
});
```

---

🤖 Создано с помощью [Claude Code](https://claude.ai/code)