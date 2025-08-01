# 📚 API Документация

## Основные endpoints

### Чат с AI
```http
POST /api/v1/conversation/chat
Content-Type: application/json

{
  "message": "Где мой заказ №12345?",
  "user_id": "user123",
  "platform": "web"
}
```

### Управление интеграциями
```http
GET /api/v1/integration/platforms
GET /api/v1/integration/connected?user_id=user123
POST /api/v1/integration/connect
```

### Webhook'и
```http
POST /api/v1/integration/webhook/{platform}
```

## Интерактивная документация

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Аутентификация

API использует токены для аутентификации. Включите токен в заголовок Authorization:

```http
Authorization: Bearer your-api-token
```

## Коды ответов

- `200` - Успешный запрос
- `400` - Неверные параметры запроса
- `401` - Неавторизованный доступ
- `404` - Ресурс не найден
- `429` - Превышен лимит запросов
- `500` - Внутренняя ошибка сервера

## Примеры использования

### Python
```python
import requests

response = requests.post(
    'http://localhost:8000/api/v1/conversation/chat',
    json={
        'message': 'Привет!',
        'user_id': 'user123',
        'platform': 'web'
    },
    headers={'Authorization': 'Bearer your-token'}
)

print(response.json())
```

### cURL
```bash
curl -X POST http://localhost:8000/api/v1/conversation/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{"message": "Привет!", "user_id": "user123", "platform": "web"}'
```