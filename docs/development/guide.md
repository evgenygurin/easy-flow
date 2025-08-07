# Руководство разработки

Требования
- Python 3.12+, uv, Docker/Compose, Redis, (PostgreSQL по мере необходимости)

Быстрый старт
```bash
uv sync
uv run uvicorn main:app --reload
# или
make install-dev
make dev
```

Качество кода
- Линтер/форматтер: Ruff; типы: MyPy; тесты: pytest/pytest-asyncio; безопасность: Bandit, Safety
```bash
make format
make lint
make test
make test-cov
make check  # полный цикл
```

Pre-commit
```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Стиль и соглашения
- Чистая архитектура: тонкие роуты → контроллеры → сервисы
- Именование осмысленное, ранние возвраты, обработка ошибок/краевых случаев
- Логи с `structlog`; не хранить секреты в коде

Тесты
- Располагать в `tests/`, именование `test_*.py`
- Покрывать состояния Flow, NLP интерпретацию, AI fallback‑ы, API контроллеры

Локальные переменные окружения
- `.env` (см. README переменные для OpenAI/YandexGPT/интеграций)
