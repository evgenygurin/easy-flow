# 🛒 E-commerce интеграции

## Поддерживаемые платформы

### Wildberries
Российский маркетплейс

**Настройка:**
```bash
WILDBERRIES_API_KEY=your-wb-api-key
```

**Возможности:**
- Получение информации о заказах
- Обновление статусов
- Синхронизация товаров
- Аналитика продаж

### Ozon
Российская e-commerce платформа

**Настройка:**
```bash
OZON_API_KEY=your-ozon-api-key
OZON_CLIENT_ID=your-client-id
```

**Возможности:**
- Управление заказами
- Обработка возвратов
- Синхронизация каталога
- Отчеты по продажам

### 1C-Bitrix
CRM и e-commerce решение

**Настройка:**
```bash
BITRIX_WEBHOOK_URL=https://your-portal.bitrix24.ru/rest/1/webhook_key/
```

**Возможности:**
- Синхронизация клиентов
- Управление сделками
- Обработка лидов
- CRM интеграция

### Shopify
Международная e-commerce платформа

**Настройка:**
```bash
SHOPIFY_SHOP_DOMAIN=your-shop.myshopify.com
SHOPIFY_ACCESS_TOKEN=your-access-token
```

**Возможности:**
- Международные продажи
- Многоязычная поддержка
- Управление инвентарем
- Обработка платежей

### WooCommerce
WordPress e-commerce плагин

**Настройка:**
```bash
WOOCOMMERCE_URL=https://your-site.com
WOOCOMMERCE_CONSUMER_KEY=ck_...
WOOCOMMERCE_CONSUMER_SECRET=cs_...
```

**Возможности:**
- Интеграция с WordPress
- Гибкая настройка
- Множество плагинов
- SEO оптимизация

## API Endpoints

### Получение платформ
```http
GET /api/v1/integration/platforms
```

### Подключение платформы
```http
POST /api/v1/integration/connect
Content-Type: application/json

{
  "platform": "wildberries",
  "api_key": "your-api-key",
  "user_id": "user123"
}
```

### Webhook для заказов
```http
POST /api/v1/integration/webhook/wildberries
Content-Type: application/json

{
  "event": "order_created",
  "order_id": "WB123456",
  "customer_id": "customer789",
  "data": { ... }
}
```

## Обработка событий

Система автоматически обрабатывает следующие события:
- Новые заказы
- Изменения статусов
- Возвраты и отмены
- Вопросы клиентов
- Отзывы и рейтинги

## Настройка уведомлений

Для каждой платформы можно настроить:
- Типы событий для уведомлений
- Шаблоны ответов
- Эскалация к оператору
- Автоматические действия