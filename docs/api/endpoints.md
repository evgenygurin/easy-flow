# API Endpoints

База: `http://localhost:8000`
- Документация: `/docs`
- ReDoc: `/redoc`
- Health: `/health/`

## Conversation
POST `/api/v1/conversation/chat`
Пример запроса:
```json
{
  "message": "Где мой заказ №12345?",
  "user_id": "user123",
  "session_id": "optional",
  "platform": "web",
  "context": {}
}
```
Пример ответа:
```json
{
  "message": "Ваш заказ №12345...",
  "session_id": "...",
  "intent": "order_status",
  "entities": {"order_number": "12345"},
  "confidence": 0.95,
  "requires_human": false,
  "suggested_actions": ["Проверить статус заказа"],
  "current_state": "order",
  "state_transitions": 2
}
```

## Integration
- GET `/api/v1/integration/platforms`
- GET `/api/v1/integration/connected?user_id=...`
- POST `/api/v1/integration/connect`
- DELETE `/api/v1/integration/disconnect/{platform_id}`
- POST `/api/v1/integration/sync/{platform_id}`
- POST `/api/v1/integration/sync-all`
- POST `/api/v1/integration/webhook/{platform}`

## Health
- GET `/health/`

Безопасность
- CORS на основе `ALLOWED_HOSTS`.
- Секреты и ключи — через `.env` (см. README и `app/core/config.py`).
