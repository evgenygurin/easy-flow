# 🔌 Интеграции и потоки данных

## Обзор интеграций

Easy Flow поддерживает интеграции с различными платформами через унифицированный интерфейс адаптеров.

### Типы интеграций

1. **E-commerce платформы** - Wildberries, Ozon, 1C-Bitrix, Shopify
2. **Мессенджеры** - Telegram, WhatsApp, VK, Viber  
3. **AI сервисы** - OpenAI GPT, YandexGPT, Anthropic Claude
4. **Платежные системы** - YooKassa, Stripe, PayPal
5. **Аналитика** - Google Analytics, Яндекс.Метрика

## Архитектура интеграций

### Диаграмма потоков данных

```
External APIs          Adapter Layer           Service Layer           Data Layer
┌─────────────┐        ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│ Wildberries │────────│ WB Adapter  │        │             │        │             │
├─────────────┤        ├─────────────┤        │             │        │             │
│ Ozon        │────────│ Ozon Adapter│        │             │        │             │
├─────────────┤        ├─────────────┤────────│ Integration │────────│ PostgreSQL  │
│ 1C-Bitrix   │────────│ Bitrix      │        │   Service   │        │   Database  │
├─────────────┤        │ Adapter     │        │             │        │             │
│ Shopify     │────────│ Shopify     │        │             │        │             │
└─────────────┘        │ Adapter     │        └─────────────┘        └─────────────┘
                       └─────────────┘

┌─────────────┐        ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│ Telegram    │────────│ Telegram    │        │             │        │             │
├─────────────┤        │ Adapter     │        │             │        │             │
│ WhatsApp    │────────├─────────────┤────────│ Messaging   │────────│    Redis    │
├─────────────┤        │ WhatsApp    │        │   Service   │        │    Cache    │
│ VK          │────────│ Adapter     │        │             │        │             │
├─────────────┤        ├─────────────┤        │             │        │             │
│ Viber       │────────│ VK/Viber    │        │             │        │             │
└─────────────┘        │ Adapters    │        └─────────────┘        └─────────────┘
                       └─────────────┘
```

## E-commerce интеграции

### Wildberries Integration

#### Конфигурация
```python
class WildberriesConfig(BaseConfig):
    api_key: str
    supplier_id: str
    base_url: str = "https://suppliers-api.wildberries.ru"
    rate_limit: int = 100  # запросов в минуту
```

#### Доступные методы
```python
class WildberriesAdapter(EcommerceAdapter):
    async def get_orders(
        self, 
        filters: OrderFilters = None,
        limit: int = 1000
    ) -> list[Order]:
        """Получение заказов с WB."""
        
    async def get_order_details(self, order_id: str) -> OrderDetails:
        """Детали заказа."""
        
    async def get_products(
        self, 
        filters: ProductFilters = None
    ) -> list[Product]:
        """Список товаров."""
        
    async def update_product_stock(
        self, 
        product_id: str, 
        quantity: int
    ) -> bool:
        """Обновление остатков."""
        
    async def get_analytics(
        self, 
        date_from: date, 
        date_to: date
    ) -> AnalyticsData:
        """Аналитические данные."""
```

#### Поток данных WB
```
WB API ──→ WB Adapter ──→ Integration Service ──→ Database
   │                          │
   │                          ▼
   │                    Conversation Service
   │                          │
   │                          ▼
   └──── Webhook ──→ Message Processing ──→ User Response
```

#### Пример использования
```python
# Получение заказов
wb_adapter = WildberriesAdapter(
    api_key=credentials["api_key"],
    supplier_id=credentials["supplier_id"]
)

orders = await wb_adapter.get_orders(
    filters=OrderFilters(
        status="new",
        date_from=date(2024, 1, 1)
    )
)

for order in orders:
    # Сохранение в базу
    await order_repository.save(order)
    
    # Отправка уведомления клиенту
    if order.status == "shipped":
        await messaging_service.send_notification(
            user_id=order.user_id,
            template="order_shipped",
            data={"order_id": order.id}
        )
```

### Ozon Integration

#### API endpoints
```python
class OzonAdapter(EcommerceAdapter):
    BASE_URL = "https://api-seller.ozon.ru"
    
    async def get_orders(self) -> list[Order]:
        """POST /v3/posting/fbs/list"""
        
    async def get_products(self) -> list[Product]:
        """POST /v2/product/list"""
        
    async def update_stock(self, product_id: str, stock: int) -> bool:
        """POST /v1/product/import/stocks"""
```

### 1C-Bitrix Integration

#### CRM интеграция
```python
class BitrixAdapter(CRMAdapter):
    async def sync_contacts(self) -> list[Contact]:
        """Синхронизация контактов."""
        
    async def create_deal(self, deal_data: DealData) -> str:
        """Создание сделки."""
        
    async def get_company_info(self, company_id: str) -> Company:
        """Информация о компании."""
```

## Messaging интеграции

### Telegram Bot Integration

#### Настройка webhook
```python
# Регистрация webhook
await bot.set_webhook(
    url=f"{settings.webhook_base_url}/api/v1/messaging/webhook/telegram",
    secret_token=settings.telegram_webhook_secret,
    allowed_updates=["message", "callback_query", "inline_query"]
)
```

#### Обработка сообщений
```python
class TelegramAdapter(MessagingAdapter):
    async def receive_webhook(
        self, 
        payload: dict[str, Any], 
        signature: str | None = None
    ) -> list[UnifiedMessage]:
        # Верификация подписи
        if not self._verify_signature(payload, signature):
            raise SecurityError("Invalid webhook signature")
            
        messages = []
        
        # Обработка обычного сообщения
        if "message" in payload:
            tg_message = payload["message"]
            unified_message = self._convert_telegram_message(tg_message)
            messages.append(unified_message)
            
        # Обработка callback query
        if "callback_query" in payload:
            callback = payload["callback_query"]
            unified_message = self._convert_callback_query(callback)
            messages.append(unified_message)
            
        return messages
    
    async def send_message(
        self, 
        chat_id: str, 
        message: UnifiedMessage, 
        priority: int = 0
    ) -> DeliveryResult:
        try:
            # Конвертация в Telegram формат
            tg_data = self._convert_to_telegram_format(message)
            
            # Отправка через Bot API
            if message.inline_keyboard:
                sent = await self.bot.send_message(
                    chat_id=int(chat_id),
                    text=tg_data["text"],
                    reply_markup=tg_data["reply_markup"],
                    parse_mode=ParseMode.HTML
                )
            else:
                sent = await self.bot.send_message(
                    chat_id=int(chat_id),
                    text=tg_data["text"],
                    parse_mode=ParseMode.HTML
                )
                
            return DeliveryResult(
                message_id=message.message_id,
                platform_message_id=str(sent.message_id),
                platform="telegram",
                status=DeliveryStatus.SENT,
                success=True,
                sent_at=datetime.now()
            )
            
        except TelegramError as e:
            return DeliveryResult(
                message_id=message.message_id,
                platform="telegram",
                status=DeliveryStatus.FAILED,
                success=False,
                error_message=str(e)
            )
```

### WhatsApp Business Integration

#### Конфигурация
```python
class WhatsAppConfig(BaseConfig):
    access_token: str
    phone_number_id: str
    webhook_verify_token: str
    webhook_secret: str
    base_url: str = "https://graph.facebook.com/v18.0"
```

#### Отправка шаблонных сообщений
```python
async def send_template_message(
    self, 
    chat_id: str, 
    template_name: str, 
    parameters: list[str]
) -> DeliveryResult:
    """Отправка шаблонного сообщения WhatsApp."""
    
    data = {
        "messaging_product": "whatsapp",
        "to": chat_id,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "ru"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": param} 
                        for param in parameters
                    ]
                }
            ]
        }
    }
    
    response = await self.http_client.post(
        f"{self.base_url}/{self.phone_number_id}/messages",
        json=data,
        headers={"Authorization": f"Bearer {self.access_token}"}
    )
    
    if response.status_code == 200:
        result = response.json()
        return DeliveryResult(
            platform_message_id=result["messages"][0]["id"],
            status=DeliveryStatus.SENT,
            success=True
        )
```

### VK Bot Integration

#### Callback API
```python
class VKAdapter(MessagingAdapter):
    async def receive_webhook(
        self, 
        payload: dict[str, Any], 
        signature: str | None = None
    ) -> list[UnifiedMessage]:
        # Обработка подтверждения
        if payload.get("type") == "confirmation":
            return []  # Возвращает confirmation_token
            
        # Обработка нового сообщения
        if payload.get("type") == "message_new":
            vk_message = payload["object"]["message"]
            return [self._convert_vk_message(vk_message)]
            
        return []
```

## AI Service интеграции

### OpenAI Integration

#### Конфигурация модели
```python
class OpenAIConfig(BaseConfig):
    api_key: str
    model: str = "gpt-4o-mini"
    max_tokens: int = 1000
    temperature: float = 0.7
    timeout: int = 30
```

#### Генерация ответов
```python
class OpenAIAdapter(AIAdapter):
    async def generate_response(
        self, 
        messages: list[Message], 
        context: ConversationContext
    ) -> AIResponse:
        
        # Подготовка системного промпта
        system_prompt = self._build_system_prompt(context)
        
        # Конвертация в формат OpenAI
        openai_messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        for msg in messages[-10:]:  # Последние 10 сообщений
            openai_messages.append({
                "role": "user" if msg.role == MessageRole.USER else "assistant",
                "content": msg.content
            })
            
        # Вызов API
        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=openai_messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            timeout=self.config.timeout
        )
        
        return AIResponse(
            content=response.choices[0].message.content,
            model=self.config.model,
            usage=TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens
            )
        )
```

### YandexGPT Integration

#### Специфичные особенности
```python
class YandexGPTAdapter(AIAdapter):
    BASE_URL = "https://llm.api.cloud.yandex.net"
    
    async def generate_response(
        self, 
        messages: list[Message], 
        context: ConversationContext
    ) -> AIResponse:
        
        # YandexGPT специфичный формат
        request_data = {
            "modelUri": f"gpt://{self.folder_id}/{self.model_name}",
            "completionOptions": {
                "stream": False,
                "temperature": self.temperature,
                "maxTokens": self.max_tokens
            },
            "messages": self._convert_messages(messages)
        }
        
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        response = await self.http_client.post(
            f"{self.BASE_URL}/foundationModels/v1/completion",
            json=request_data,
            headers=headers
        )
```

## Синхронизация данных

### Поток синхронизации

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Scheduler      │    │  Sync Service   │    │   Adapters      │
│  (Celery/APScheduler)│  (Orchestrator) │    │ (Platform APIs) │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │ 1. Trigger sync      │                      │
          ├─────────────────────▶│                      │
          │                      │ 2. Get integration   │
          │                      │    credentials       │
          │                      ├─────────────────────▶│
          │                      │                      │ 3. Fetch data
          │                      │◀─────────────────────┤    from API
          │                      │                      │
          │                      │ 4. Process & store   │
          │                      │    data              │
          │                      │────────────────┐     │
          │                      │                │     │
          │                      │◀───────────────┘     │
          │ 5. Update status     │                      │
          │◀─────────────────────┤                      │
          │                      │                      │
```

### Планировщик синхронизации

```python
class SyncScheduler:
    def __init__(self, integration_service: IntegrationService):
        self.integration_service = integration_service
        self.scheduler = AsyncIOScheduler()
        
    async def start(self):
        """Запуск планировщика."""
        # Синхронизация заказов каждые 15 минут
        self.scheduler.add_job(
            self.sync_all_orders,
            'interval',
            minutes=15,
            id='sync_orders'
        )
        
        # Синхронизация товаров каждый час
        self.scheduler.add_job(
            self.sync_all_products,
            'interval',
            hours=1,
            id='sync_products'
        )
        
        self.scheduler.start()
        
    async def sync_all_orders(self):
        """Синхронизация заказов для всех активных интеграций."""
        integrations = await self.integration_service.get_active_integrations(
            platform_type=PlatformType.ECOMMERCE
        )
        
        for integration in integrations:
            try:
                await self.integration_service.sync_orders(
                    integration_id=integration.id,
                    sync_type=SyncType.INCREMENTAL
                )
            except Exception as e:
                logger.error(
                    "Order sync failed",
                    integration_id=integration.id,
                    error=str(e)
                )
```

### Error Handling и Retry логика

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((ConnectionError, TimeoutError))
)
async def sync_orders_with_retry(
    self, 
    integration: Integration
) -> SyncResult:
    """Синхронизация с повторными попытками."""
    
    adapter = self.adapter_factory.get_adapter(integration.platform_id)
    
    try:
        # Получение данных из внешнего API
        orders = await adapter.get_orders(
            credentials=integration.credentials,
            last_sync=integration.last_sync_at
        )
        
        # Сохранение в базу
        saved_count = 0
        errors = []
        
        for order in orders:
            try:
                await self.order_repository.upsert(order)
                saved_count += 1
            except Exception as e:
                errors.append({
                    "order_id": order.id,
                    "error": str(e)
                })
                
        # Обновление статуса интеграции
        await self.integration_repository.update_sync_status(
            integration_id=integration.id,
            last_sync_at=datetime.now(),
            sync_result=SyncResult(
                records_synced=saved_count,
                errors=errors
            )
        )
        
        return SyncResult(
            success=True,
            records_synced=saved_count,
            errors=errors
        )
        
    except Exception as e:
        logger.error(
            "Sync failed",
            integration_id=integration.id,
            error=str(e)
        )
        
        await self.integration_repository.update_sync_status(
            integration_id=integration.id,
            sync_result=SyncResult(
                success=False,
                error_message=str(e)
            )
        )
        
        raise
```

## Webhooks

### Универсальный webhook handler

```python
@router.post("/webhook/{platform}")
async def handle_webhook(
    platform: str,
    request: Request,
    messaging_controller: MessagingController = Depends()
):
    """Универсальная обработка webhooks от всех платформ."""
    
    # Получение payload
    if request.headers.get("content-type") == "application/json":
        payload = await request.json()
    else:
        payload = await request.form()
        
    # Получение подписи для верификации
    signature = request.headers.get("x-signature") or \
               request.headers.get("x-hub-signature-256") or \
               request.headers.get("x-telegram-bot-api-secret-token")
    
    # Создание webhook запроса
    webhook_request = WebhookRequest(
        platform=platform,
        payload=payload,
        signature=signature,
        headers=dict(request.headers)
    )
    
    # Обработка через контроллер
    result = await messaging_controller.process_webhook(webhook_request)
    
    # Платформо-специфичные ответы
    if platform == "telegram":
        return {"ok": True}
    elif platform == "whatsapp":
        return {"status": "ok"}
    elif platform == "vk":
        if payload.get("type") == "confirmation":
            return settings.vk_confirmation_token
        return "ok"
    
    return result
```

### Безопасность webhooks

```python
class WebhookSecurity:
    @staticmethod
    def verify_telegram_signature(
        payload: dict, 
        signature: str, 
        secret: str
    ) -> bool:
        """Верификация подписи Telegram webhook."""
        if not signature:
            return False
            
        expected = hmac.new(
            secret.encode(),
            json.dumps(payload, separators=(',', ':')).encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
    
    @staticmethod  
    def verify_whatsapp_signature(
        payload: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """Верификация подписи WhatsApp webhook."""
        if not signature.startswith("sha256="):
            return False
            
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        received = signature.removeprefix("sha256=")
        return hmac.compare_digest(expected, received)
```

## Мониторинг интеграций

### Метрики
```python
class IntegrationMetrics:
    def __init__(self, prometheus_registry):
        self.api_calls = Counter(
            'integration_api_calls_total',
            'Total API calls to external platforms',
            ['platform', 'method', 'status'],
            registry=prometheus_registry
        )
        
        self.response_time = Histogram(
            'integration_api_response_seconds',
            'API response time in seconds',
            ['platform', 'method'],
            registry=prometheus_registry
        )
        
        self.sync_success = Counter(
            'integration_sync_success_total',
            'Successful sync operations',
            ['platform', 'sync_type'],
            registry=prometheus_registry
        )
        
    def record_api_call(
        self, 
        platform: str, 
        method: str, 
        status: str,
        duration: float
    ):
        self.api_calls.labels(
            platform=platform,
            method=method,
            status=status
        ).inc()
        
        self.response_time.labels(
            platform=platform,
            method=method
        ).observe(duration)
```

### Health Checks
```python
@router.get("/health/integrations")
async def integration_health_check(
    integration_service: IntegrationService = Depends()
):
    """Проверка состояния интеграций."""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "integrations": {}
    }
    
    # Проверка каждой платформы
    for platform in ["wildberries", "ozon", "telegram", "whatsapp"]:
        try:
            # Простая проверка доступности API
            adapter = adapter_factory.get_adapter(platform)
            status = await adapter.health_check()
            
            health_status["integrations"][platform] = {
                "status": "healthy" if status else "unhealthy",
                "last_check": datetime.now().isoformat()
            }
            
        except Exception as e:
            health_status["integrations"][platform] = {
                "status": "error",
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }
            health_status["status"] = "degraded"
    
    return health_status
```

---

🤖 Создано с помощью [Claude Code](https://claude.ai/code)