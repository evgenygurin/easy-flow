# 📊 Мониторинг и аналитика

## Основные метрики

### Производительность AI
- **Время ответа AI** - среднее время генерации ответа
- **Точность распознавания намерений** - процент правильно определенных интентов
- **Качество ответов** - оценка пользователями полезности ответов
- **Количество эскалаций к операторам** - когда AI не смог помочь

### Бизнес метрики
- **Удовлетворенность клиентов** - NPS и CSAT scores
- **Конверсия диалогов** - процент диалогов, завершившихся действием
- **Время разрешения запросов** - от получения до решения
- **Количество повторных обращений** - индикатор качества поддержки

### Технические метрики
- **Uptime сервисов** - доступность API и интеграций
- **Пропускная способность** - RPS (requests per second)
- **Использование ресурсов** - CPU, RAM, disk usage
- **Ошибки и исключения** - количество и типы ошибок

## Настройка логирования

### Structured Logging
```python
import structlog

logger = structlog.get_logger()

# Пример логирования
logger.info(
    "Обработка сообщения",
    user_id=user_id,
    platform="telegram",
    intent=detected_intent,
    response_time=response_time_ms,
    ai_model="gpt-4"
)
```

### Уровни логирования
- **DEBUG** - детальная информация для отладки
- **INFO** - общая информация о работе системы
- **WARNING** - предупреждения о проблемах
- **ERROR** - ошибки, требующие внимания
- **CRITICAL** - критические ошибки, требующие немедленного вмешательства

### Форматы логов
```json
{
    "timestamp": "2024-01-15T10:30:00Z",
    "level": "INFO",
    "service": "conversation-service",
    "user_id": "user123",
    "session_id": "sess456",
    "event": "message_processed",
    "platform": "telegram",
    "intent": "order_status",
    "confidence": 0.95,
    "response_time_ms": 245,
    "ai_tokens_used": 150,
    "cost_usd": 0.003
}
```

## Система мониторинга

### Prometheus + Grafana
```python
# Метрики в коде
from prometheus_client import Counter, Histogram, Gauge

# Счетчики
message_counter = Counter('messages_total', 'Total messages processed', ['platform', 'intent'])
error_counter = Counter('errors_total', 'Total errors', ['error_type', 'service'])

# Гистограммы для времени
response_time = Histogram('response_time_seconds', 'Response time', ['service', 'endpoint'])

# Gauges для текущих значений
active_sessions = Gauge('active_sessions', 'Current active sessions')

# Использование
message_counter.labels(platform='telegram', intent='order_status').inc()
with response_time.labels(service='ai', endpoint='/chat').time():
    # Обработка запроса
    pass
```

### Health Checks
```python
# app/api/routes/health.py
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0",
        "services": {
            "database": await check_database(),
            "redis": await check_redis(),
            "ai_service": await check_ai_service(),
        }
    }

@router.get("/health/db")
async def database_health():
    try:
        # Проверка подключения к БД
        await database.execute("SELECT 1")
        return {"status": "healthy", "latency_ms": latency}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

## Алерты и уведомления

### Критические алерты
- **API недоступен** > 1 минуты
- **Ошибки** > 5% от общего трафика
- **Время ответа** > 10 секунд
- **Использование диска** > 85%
- **Память** > 90%

### Бизнес алерты
- **Падение удовлетворенности** < 4.0/5.0
- **Рост эскалаций** > 20% от обычного
- **Критические отзывы** с негативными ключевыми словами

### Настройка алертов
```yaml
# alertmanager.yml
groups:
- name: easy-flow
  rules:
  - alert: HighErrorRate
    expr: rate(errors_total[5m]) > 0.05
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value }} errors per second"

  - alert: SlowResponseTime
    expr: histogram_quantile(0.95, response_time_seconds) > 10
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Slow response time"
      description: "95th percentile response time is {{ $value }}s"
```

## Дашборды

### Операционный дашборд
- Текущий RPS и статусы API
- Ошибки в реальном времени
- Использование ресурсов
- Активные сессии

### Бизнес дашборд
- Количество диалогов по платформам
- Топ интентов и проблем
- Удовлетворенность клиентов
- Конверсия в действия

### AI Performance дашборд
- Время ответа AI моделей
- Использование токенов и стоимость
- Точность распознавания интентов
- Качество генерируемых ответов

## Аналитика данных

### Сбор данных
```python
# Модель для хранения метрик
class ConversationMetrics(Base):
    __tablename__ = "conversation_metrics"
    
    id = Column(UUID, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String)
    platform = Column(String)
    intent = Column(String)
    confidence = Column(Float)
    response_time_ms = Column(Integer)
    tokens_used = Column(Integer)
    cost_usd = Column(Numeric(10, 4))
    satisfaction_score = Column(Integer)  # 1-5
    resolved = Column(Boolean, default=False)
```

### Отчеты
- **Ежедневные** - краткая сводка метрик
- **Еженедельные** - тренды и аномалии
- **Ежемесячные** - полный анализ и рекомендации

### Экспорт данных
```python
@router.get("/analytics/export")
async def export_analytics(
    start_date: date,
    end_date: date,
    format: str = "json"  # json, csv, xlsx
):
    data = await get_analytics_data(start_date, end_date)
    
    if format == "csv":
        return create_csv_response(data)
    elif format == "xlsx":
        return create_excel_response(data)
    else:
        return data
```

## Мониторинг интеграций

### Внешние сервисы
- Доступность API партнеров
- Время ответа webhook'ов
- Ошибки аутентификации
- Лимиты использования API

### SLA мониторинг
```python
# Отслеживание SLA
class SLAMetrics:
    def __init__(self):
        self.uptime_target = 0.999  # 99.9%
        self.response_time_target = 2.0  # 2 секунды
        
    async def check_sla_compliance(self):
        current_uptime = await calculate_uptime()
        avg_response_time = await calculate_avg_response_time()
        
        return {
            "uptime": {
                "current": current_uptime,
                "target": self.uptime_target,
                "compliant": current_uptime >= self.uptime_target
            },
            "response_time": {
                "current": avg_response_time,
                "target": self.response_time_target,
                "compliant": avg_response_time <= self.response_time_target
            }
        }
```

## Оптимизация производительности

### Кэширование
- Redis для частых запросов
- Application-level кэширование
- CDN для статических ресурсов

### Масштабирование
- Горизонтальное масштабирование через Docker
- Load balancing
- Auto-scaling на основе метрик

### Профилирование
```python
import cProfile
import pstats

def profile_function(func):
    def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        result = func(*args, **kwargs)
        pr.disable()
        
        stats = pstats.Stats(pr)
        stats.sort_stats('cumulative')
        stats.print_stats(10)  # Топ 10 медленных функций
        
        return result
    return wrapper
```