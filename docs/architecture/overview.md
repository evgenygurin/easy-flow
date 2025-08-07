# Архитектурный обзор

Ключевая идея: модульная AI‑платформа поддержки клиентов e‑commerce с управляемым диалоговым потоком (state machine), тонким HTTP‑слоем и четким разделением ответственности: API → Controllers → Services → Repositories/Adapters.

- Основной артефакт: Conversation Flow как управляемая машина состояний с контекстом и эскалацией.
- Бизнес‑ядро: `NLPService` (интенты/сущности) + `AIService` (шаблоны, KB, LLM) + `ConversationService` (оркестрация) + `ConversationFlowService` (состояния).
- Интеграции: `adapters/*` для e‑commerce/мессенджеров/платежей; абстракции сверху — `IntegrationService`.
- Доступ к данным: `repositories/*` (интерфейсы + реализации SQLAlchemy), `models/*` — доменные модели.
- Конфигурация: `app/core/config.py` на `pydantic-settings`.

Структура слоёв (Clean Architecture):
- Presentation: `app/api` (FastAPI: роуты минимальны, контроллеры держат HTTP‑логику)
- Domain/Business: `app/services` (NLP/AI/Flow/Integration/Embeddings/Cache)
- Data: `app/repositories` (интерфейсы/SQLAlchemy), `app/models`
- Integrations: `app/adapters` (russian/international)

Нефункциональные требования:
- Язык: русский по умолчанию; fallback на EN в NLP.
- Надёжность: эскалация к оператору при низкой уверенности/циклах/ошибках.
- Производительность: кэширование ответов AI, embeddings‑поиск по KB.
- Тестируемость: модульные/интеграционные тесты (pytest, pytest‑asyncio).
- Наблюдаемость: структурное логирование (structlog), метрики Flow.

Ключевые компоненты
- NLP: паттерны интентов и извлечение сущностей (+ текстовая эвристика языка/тональности).
- AI: шаблоны → KB → LLM (OpenAI/YandexGPT) с кэшированием; embeddings‑индекс знаний.
- Flow: состояния `hello/order/payment/shipping/hangup`, контекст сессии, метаданные для эскалации, метрики распределения.
- API: `/api/v1/conversation/*`, `/api/v1/integration/*`, `/health`.
- Конфигурация и секреты: переменные окружения `.env` (см. README).

Границы MVP
- Диалог по core‑сценариям (приветствие, заказ, доставка, оплата, завершение) с эскалацией.
- NLP на паттернах + простая тональность.
- AI: шаблоны и KB как baseline; LLM как fallback.
- Базовые метрики Flow и health endpoint.

Неголосуемые решения
- Тонкие маршруты и вынесение логики в контроллеры/сервисы.
- State machine для управления диалогом вместо «монолитной» генерации.
- Репозиторный слой под БД для последующей персистентности.
