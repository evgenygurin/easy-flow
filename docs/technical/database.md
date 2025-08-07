# 🗄️ База данных Easy Flow

## Обзор архитектуры БД

Easy Flow использует **PostgreSQL** как основную базу данных и **Redis** для кэширования и сессий.

### Технологии
- **PostgreSQL 15+** - основная реляционная БД
- **Redis 7+** - кэш, сессии, очереди задач
- **SQLAlchemy 2.0** - ORM с async поддержкой
- **Alembic** - миграции схемы

## Схема базы данных

### Диаграмма ER

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│      users      │    │   integrations  │    │   platforms     │
│─────────────────│    │─────────────────│    │─────────────────│
│ id (PK)         │───┐│ id (PK)         │ ┌──│ id (PK)         │
│ email           │   ││ user_id (FK)    │─┘  │ name            │
│ name            │   ││ platform_id (FK)│────│ display_name    │
│ created_at      │   ││ credentials     │    │ type            │
│ updated_at      │   ││ settings        │    │ region          │
│ is_active       │   ││ status          │    │ capabilities    │
└─────────────────┘   ││ created_at      │    └─────────────────┘
                      ││ updated_at      │
┌─────────────────┐   │└─────────────────┘
│   conversations │   │
│─────────────────│   │
│ id (PK)         │   │  ┌─────────────────┐
│ session_id      │   │  │    messages     │
│ user_id (FK)    │───┘  │─────────────────│
│ platform        │      │ id (PK)         │
│ status          │   ┌──│ conversation_id │
│ context_data    │   │  │ session_id      │
│ created_at      │   │  │ user_id (FK)    │
│ updated_at      │   │  │ content         │
└─────────────────┘   │  │ role            │
          │           │  │ platform        │
          └───────────┘  │ intent          │
                         │ entities        │
                         │ confidence      │
                         │ metadata        │
                         │ created_at      │
                         └─────────────────┘

┌─────────────────┐    ┌─────────────────┐
│ platform_metrics│    │   sync_logs     │
│─────────────────│    │─────────────────│
│ id (PK)         │    │ id (PK)         │
│ integration_id  │    │ integration_id  │
│ metric_type     │    │ sync_type       │
│ metric_value    │    │ status          │
│ recorded_at     │    │ records_synced  │
└─────────────────┘    │ errors          │
                       │ started_at      │
                       │ completed_at    │
                       └─────────────────┘
```

## Таблицы

### users
Пользователи системы.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    language_code VARCHAR(10) DEFAULT 'ru',
    timezone VARCHAR(50) DEFAULT 'Europe/Moscow',
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_is_active ON users(is_active);
CREATE INDEX idx_users_created_at ON users(created_at);
```

### platforms  
Доступные платформы для интеграции.

```sql
CREATE TYPE platform_type AS ENUM ('ecommerce', 'messaging', 'voice', 'analytics');
CREATE TYPE platform_region AS ENUM ('russia', 'international', 'global');

CREATE TABLE platforms (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    type platform_type NOT NULL,
    region platform_region NOT NULL,
    capabilities TEXT[] DEFAULT '{}',
    required_credentials TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    configuration JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Данные платформ
INSERT INTO platforms VALUES 
('wildberries', 'Wildberries', 'Wildberries', 'ecommerce', 'russia', 
 '{"orders", "products", "analytics"}', '{"api_key", "supplier_id"}', true),
('ozon', 'Ozon', 'Ozon', 'ecommerce', 'russia',
 '{"orders", "products", "inventory"}', '{"client_id", "api_key"}', true),
('telegram', 'Telegram', 'Telegram Bot API', 'messaging', 'global',
 '{"text", "inline_keyboard", "media", "files", "voice"}', '{"bot_token"}', true),
('whatsapp', 'WhatsApp', 'WhatsApp Business', 'messaging', 'global',
 '{"text", "media", "templates", "interactive_buttons"}', '{"access_token", "phone_number_id"}', true);
```

### integrations
Подключения пользователей к платформам.

```sql
CREATE TYPE integration_status AS ENUM ('pending', 'connected', 'error', 'disconnected');

CREATE TABLE integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform_id VARCHAR(50) NOT NULL REFERENCES platforms(id),
    
    -- Зашифрованные credentials
    credentials_encrypted BYTEA,
    encryption_key_id VARCHAR(255),
    
    -- Настройки интеграции
    settings JSONB DEFAULT '{}',
    
    -- Статус
    status integration_status DEFAULT 'pending',
    status_message TEXT,
    
    -- Синхронизация
    last_sync_at TIMESTAMP WITH TIME ZONE,
    next_sync_at TIMESTAMP WITH TIME ZONE,
    sync_interval_minutes INTEGER DEFAULT 60,
    
    -- Метаданные
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Ограничение: один пользователь - одна платформа
    UNIQUE(user_id, platform_id)
);

-- Индексы
CREATE INDEX idx_integrations_user_id ON integrations(user_id);
CREATE INDEX idx_integrations_platform_id ON integrations(platform_id);
CREATE INDEX idx_integrations_status ON integrations(status);
CREATE INDEX idx_integrations_next_sync ON integrations(next_sync_at) 
    WHERE status = 'connected';
```

### conversations
Диалоги пользователей.

```sql
CREATE TYPE conversation_status AS ENUM ('active', 'paused', 'closed', 'escalated');

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Платформа общения
    platform VARCHAR(50) NOT NULL,
    chat_id VARCHAR(255),
    
    -- Статус и состояние
    status conversation_status DEFAULT 'active',
    current_state VARCHAR(100) DEFAULT 'initial',
    
    -- Контекстные данные
    context_data JSONB DEFAULT '{}',
    
    -- Метрики
    messages_count INTEGER DEFAULT 0,
    
    -- Временные метки
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    closed_at TIMESTAMP WITH TIME ZONE
);

-- Индексы
CREATE INDEX idx_conversations_session_id ON conversations(session_id);
CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_platform_chat ON conversations(platform, chat_id);
CREATE INDEX idx_conversations_status ON conversations(status);
CREATE INDEX idx_conversations_updated_at ON conversations(updated_at);
```

### messages
Сообщения в диалогах.

```sql
CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system');
CREATE TYPE message_direction AS ENUM ('inbound', 'outbound');

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Связи
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    session_id VARCHAR(255) NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Содержимое
    content TEXT NOT NULL,
    role message_role NOT NULL,
    direction message_direction,
    
    -- Платформа
    platform VARCHAR(50) NOT NULL,
    platform_message_id VARCHAR(255),
    
    -- NLP данные
    intent VARCHAR(100),
    entities JSONB DEFAULT '{}',
    confidence DECIMAL(3,2),
    
    -- Метаданные
    metadata JSONB DEFAULT '{}',
    
    -- Время
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_platform_message ON messages(platform, platform_message_id);
CREATE INDEX idx_messages_intent ON messages(intent);
CREATE INDEX idx_messages_created_at ON messages(created_at);

-- Партиционирование по дате (опционально для больших объемов)
-- CREATE TABLE messages_y2024m01 PARTITION OF messages
-- FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### sync_logs
Логи синхронизации с внешними платформами.

```sql
CREATE TYPE sync_status AS ENUM ('running', 'success', 'partial', 'failed');
CREATE TYPE sync_type AS ENUM ('full', 'incremental', 'orders', 'products');

CREATE TABLE sync_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_id UUID NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
    
    -- Тип синхронизации
    sync_type sync_type NOT NULL,
    status sync_status NOT NULL,
    
    -- Результаты
    records_requested INTEGER,
    records_synced INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    
    -- Ошибки
    errors JSONB DEFAULT '[]',
    error_message TEXT,
    
    -- Время выполнения
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    
    -- Метаданные
    metadata JSONB DEFAULT '{}'
);

-- Индексы
CREATE INDEX idx_sync_logs_integration_id ON sync_logs(integration_id);
CREATE INDEX idx_sync_logs_status ON sync_logs(status);
CREATE INDEX idx_sync_logs_started_at ON sync_logs(started_at);
```

### platform_metrics
Метрики использования платформ.

```sql
CREATE TYPE metric_type AS ENUM (
    'messages_sent', 'messages_received', 'api_calls', 
    'errors', 'response_time', 'sync_duration'
);

CREATE TABLE platform_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_id UUID REFERENCES integrations(id) ON DELETE CASCADE,
    platform_id VARCHAR(50) NOT NULL REFERENCES platforms(id),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    -- Метрика
    metric_type metric_type NOT NULL,
    metric_value DECIMAL(15,4) NOT NULL,
    metric_unit VARCHAR(50), -- 'count', 'seconds', 'bytes', etc.
    
    -- Агрегация
    aggregation_period VARCHAR(20) DEFAULT 'hour', -- 'minute', 'hour', 'day'
    
    -- Временной интервал
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    period_start TIMESTAMP WITH TIME ZONE,
    period_end TIMESTAMP WITH TIME ZONE,
    
    -- Дополнительные атрибуты
    attributes JSONB DEFAULT '{}'
);

-- Индексы
CREATE INDEX idx_platform_metrics_integration ON platform_metrics(integration_id);
CREATE INDEX idx_platform_metrics_platform ON platform_metrics(platform_id);
CREATE INDEX idx_platform_metrics_type_time ON platform_metrics(metric_type, recorded_at);
CREATE INDEX idx_platform_metrics_user_time ON platform_metrics(user_id, recorded_at);
```

## Модели SQLAlchemy

### User Model
```python
class User(Base):
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    language_code: Mapped[str] = mapped_column(String(10), default="ru")
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    integrations: Mapped[list["Integration"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(back_populates="user", cascade="all, delete-orphan")
```

### Integration Model
```python
class Integration(Base):
    __tablename__ = "integrations"
    
    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    platform_id: Mapped[str] = mapped_column(String(50), ForeignKey("platforms.id"), nullable=False)
    
    credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    encryption_key_id: Mapped[str | None] = mapped_column(String(255))
    
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[IntegrationStatus] = mapped_column(Enum(IntegrationStatus), default=IntegrationStatus.PENDING)
    status_message: Mapped[str | None] = mapped_column(Text)
    
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    
    metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="integrations")
    platform: Mapped["Platform"] = relationship()
    sync_logs: Mapped[list["SyncLog"]] = relationship(back_populates="integration", cascade="all, delete-orphan")
```

### Message Model
```python
class Message(Base):
    __tablename__ = "messages"
    
    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid4)
    
    conversation_id: Mapped[UUID | None] = mapped_column(UUID, ForeignKey("conversations.id"))
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[UUID] = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    
    content: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    direction: Mapped[MessageDirection | None] = mapped_column(Enum(MessageDirection))
    
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    platform_message_id: Mapped[str | None] = mapped_column(String(255))
    
    intent: Mapped[str | None] = mapped_column(String(100))
    entities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    
    metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="messages")
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
```

## Redis Schema

### Структура ключей

```
# Сессии пользователей
session:{session_id} -> {
  "user_id": "uuid",
  "platform": "telegram",
  "created_at": "2024-01-10T10:00:00Z",
  "context": {...}
}

# Кэш пользователей
user:{user_id} -> {
  "name": "Иван Петров",
  "email": "ivan@example.com",
  "preferences": {...}
}

# Кэш интеграций
integration:{user_id}:{platform_id} -> {
  "status": "connected",
  "last_sync": "2024-01-10T09:00:00Z",
  "credentials": "encrypted_data"
}

# Очереди задач
queue:sync_orders -> ["integration_id_1", "integration_id_2"]
queue:send_messages -> ["message_id_1", "message_id_2"]

# Метрики в реальном времени
metrics:{platform}:{date}:{hour} -> {
  "messages_sent": 1523,
  "messages_received": 892,
  "api_calls": 3421
}

# Rate limiting
ratelimit:{user_id}:{endpoint} -> {
  "count": 45,
  "reset": 1704794460
}
```

## Миграции

### Alembic Configuration

```python
# alembic/env.py
from app.models.database import Base
from app.core.config import get_settings

def run_migrations_online():
    settings = get_settings()
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.database_url
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
```

### Пример миграции

```python
# alembic/versions/001_initial_schema.py
"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-10 10:00:00.000000
"""

def upgrade():
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    
    # Create indexes
    op.create_index('idx_users_email', 'users', ['email'])

def downgrade():
    op.drop_table('users')
```

## Оптимизация производительности

### Индексы
- Композитные индексы для часто используемых запросов
- Partial индексы для фильтрации по статусам
- GIN индексы для JSONB полей

### Партиционирование
```sql
-- Партиционирование таблицы messages по дате
CREATE TABLE messages (
    id UUID,
    created_at TIMESTAMP WITH TIME ZONE,
    -- другие поля
) PARTITION BY RANGE (created_at);

CREATE TABLE messages_2024_01 PARTITION OF messages
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### Connection Pooling
```python
# app/core/database.py
engine = create_async_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```

### Кэширование

```python
@cache(expire=300)  # 5 минут
async def get_user_integrations(user_id: str) -> list[Integration]:
    return await integration_repository.get_by_user_id(user_id)
```

## Backup и Recovery

### Ежедневные бэкапы
```bash
# Полный дамп
pg_dump -h localhost -U postgres -d easyflow > backup_$(date +%Y%m%d).sql

# Только данные
pg_dump -h localhost -U postgres -d easyflow --data-only > data_$(date +%Y%m%d).sql
```

### Point-in-time Recovery
```bash
# Включение WAL архивирования
# postgresql.conf:
# wal_level = replica
# archive_mode = on
# archive_command = 'cp %p /path/to/archive/%f'
```

---

🤖 Создано с помощью [Claude Code](https://claude.ai/code)