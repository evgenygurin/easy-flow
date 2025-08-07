# Микросервисная архитектура платформы

Ниже — схемы контекстов, контейнеров и последовательностей для платформы (уровни C4: System/Container/Sequence). Подход к визуализации вдохновлён идеями автоматизируемой графовой визуализации архитектур ([CloudBees](https://www.cloudbees.com/blog/documenting-microservices), [Microservices Practitioner](https://articles.microservices.com/an-alternative-way-of-visualizing-microservice-architecture-837cbee575c1?gi=9a6d606207c3), [microservices.io](https://microservices.io/post/architecture/2023/01/18/omg-are-you-still-using-rational-rose.html)).

## Контекст (L1)
```mermaid
graph TD
  user["Клиент"]
  agent["Оператор (эскалация)"]
  web["Web/Widget"]
  tg["Telegram"]
  wa["WhatsApp"]
  voice["Voice Gateway (Alice/Asterisk/Tinkoff)"]

  gateway["API Gateway (FastAPI)"]

  subgraph Platform
    conv["Conversation Service (оркестрация)"]
    nlp["NLP Service"]
    ai["AI/LLM Service"]
    flow["Conversation Flow Engine"]
    kb["Knowledge Base + Embeddings"]
    integ["Integration Service"]
    notify["Notification Service"]
    metrics["Analytics/Metrics"]
    userctx["User Context Service"]
  end

  extDb[("PostgreSQL/Redis")]:::ext
  adapters["E‑commerce Adapters (WB/Ozon/Bitrix/...)"]:::ext
  pay["Payments (YooKassa)"]:::ext

  user --> web --> gateway
  user -.-> tg -.-> gateway
  user -.-> wa -.-> gateway
  user -.-> voice -.-> gateway

  gateway --> conv
  conv --> nlp
  conv --> ai
  conv --> flow
  conv --> userctx
  conv --> integ
  conv --> metrics
  ai --> kb
  nlp --> kb
  integ --> adapters
  integ --> pay
  conv --> notify

  Platform --> extDb

  classDef ext fill:#eef,stroke:#99f
```

## Контейнеры (L2)
```mermaid
graph LR
  api["API Gateway (FastAPI routes/controllers)"]
  conv["Conversation Service\n(диалоги, сессии)"]
  flow["Flow Engine\n(state machine)"]
  nlp["NLP Service\n(интенты/сущности)"]
  ai["AI Service\n(шаблоны/KB/LLM)"]
  kb["KB/Embeddings Index"]
  cache[("Redis Cache")]
  db[("PostgreSQL")] 
  integ["Integration Service"]
  adapters["Adapters: WB/Ozon/Bitrix/…"]
  payments["Payments: YooKassa"]
  channels["Channels: Telegram/WhatsApp/Webhooks"]
  metrics["Metrics/Logging"]

  api --> conv
  conv --> flow
  conv --> nlp
  conv --> ai
  conv --> integ
  conv --> metrics
  ai --> kb
  nlp --> kb
  conv --> cache
  conv --> db
  integ --> adapters
  integ --> payments
  api --> channels
```

## Последовательность: «Статус заказа» (L3)
```mermaid
sequenceDiagram
  participant U as User
  participant Ch as Channel (Web/TG/WA)
  participant API as API Gateway
  participant CONV as Conversation Service
  participant NLP as NLP
  participant FLOW as Flow Engine
  participant AI as AI/KB
  participant INT as Integration
  participant EXT as E‑commerce Adapter

  U->>Ch: Сообщение «Где мой заказ №12345?»
  Ch->>API: HTTP POST /conversation/chat
  API->>CONV: process_conversation()
  CONV->>NLP: process_message(text)
  NLP-->>CONV: intent=order_status, entities={order_number}
  CONV->>FLOW: process_conversation_flow(...)
  FLOW-->>CONV: state=order, actions
  CONV->>INT: getOrderStatus(12345)
  INT->>EXT: API call
  EXT-->>INT: status=In transit, eta=...
  INT-->>CONV: order info
  CONV->>AI: enrich response (KB/templates)
  AI-->>CONV: финальный текст
  CONV-->>API: ChatResponse (message, state, actions)
  API-->>Ch: 200 OK
  Ch-->>U: Ответ с деталями заказа
```

## Сервисные зависимости
- API ↔ Conversation: синхронный HTTP.
- Conversation ↔ (NLP/AI/Flow/Integration): синхронно, с внутренними таймаутами/ретраями.
- Integration ↔ Adapters/Payments: внешние HTTP/gRPC, требуются ретраи/ограничители.
- Хранилища: Redis (кэш), PostgreSQL (персистентность), Embeddings (в памяти/внешний векторный стор).

## Нефункциональные требования
- Наблюдаемость: метрики на вызовы, ошибки, латентность, распределение состояний.
- Надёжность: эскалация к оператору, детектор зацикливаний/длинных диалогов.
- Безопасность: секреты через ENV/Secret‑store, минимизация PII.
