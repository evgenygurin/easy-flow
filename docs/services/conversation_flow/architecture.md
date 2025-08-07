# Архитектура

Компоненты:
- `main.py` — контекст и состояния:
  - `Context`: связывает пользователя, распознавание (`Recognize`), фразы (`PromptStack`), интеграции (`Post`), и текущий `state`; управляет рекурсивным циклом request() с безопасными пределами.
  - `Main` и производные (`Hello`, `Shipping`, `Payments`, `Order`, `Hangup` и др.): содержат логику `navigation()`, `basic()`, `question()`, `handle()`.
- `command.py` — команды `TTS` и `STT` (паттерн Command) + `Invoker` для говорения/слушания через Tinkoff VoiceKit.
- `recognize.py` — детектор: `search_intents/entities/products/name/city/digit`, хранит `utterance`, выдаёт бинарные проверки `entity()/intent()/product()`.
- `patterns.py` — словари регулярных выражений: `intent`, `entity`, `product`, `name`, `city`, `context_words`.
- `prompts.py` — словарь SSML‑фраз (вариативность, локальные «антиспам» нейтрализации букв).
- `stack.py` — `PromptStack`: собирает SSML, хранит историю, управляет `say()`, `listen()`, `say_and_listen()`.
- `post.py` — интеграция с API ПР: очистка адреса и тарифы; хранит адресные поля и метод доставки.
- `models.py` — ORM (SQLAlchemy) для чтения заказов/статусов (под OpenCart), конфиг через `.env`.
- `auth.py` — JWT для VoiceKit.
- `utils.py` — утилиты (очистка, склонение дней, SMS‑заглушка).

Поток:
1) `Invoker` говорит (`TTS`) → слушает (`STT`) → `Recognize` заполняет поля → `Context` делегирует в `state.handle()`
2) `state` через `navigation/basic/question` решает переходы (`transition_to`) и ответы (`PromptStack.say*`) с возможным вызовом `Post`.
3) `Context.request()` повторяется до `Hangup` или превышения лимитов.
