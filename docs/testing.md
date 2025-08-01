# 🧪 Тестирование и качество кода

## Настройка инструментов качества кода

Проект использует современные инструменты для поддержания высокого качества кода:

### Установка pre-commit хуков
```bash
# Установите pre-commit хуки для автоматической проверки
pre-commit install

# Запуск проверки на всех файлах
pre-commit run --all-files
```

## Инструменты качества кода

### Ruff - быстрый линтер и форматтер
```bash
# Проверка и автоматическое исправление
ruff check app/ tests/ --fix

# Форматирование кода
ruff format app/ tests/
```

### Black - форматирование кода
```bash
# Форматирование
black app/ tests/

# Проверка без изменений
black --check app/ tests/
```

### MyPy - проверка типов
```bash
# Проверка типов
mypy app/ --config-file=pyproject.toml
```

### Bandit - проверка безопасности
```bash
# Проверка уязвимостей безопасности
bandit -r app/ --format json
```

### Safety - проверка зависимостей
```bash
# Проверка известных уязвимостей в зависимостях
safety check --json
```

## Запуск тестов

```bash
# Запуск всех тестов
pytest

# Запуск с покрытием кода
pytest --cov=app tests/

# Генерация HTML отчета покрытия
pytest --cov=app --cov-report=html tests/
```

## Makefile команды

```bash
# Установка зависимостей
make install

# Запуск всех проверок качества кода
make lint

# Форматирование кода
make format

# Запуск тестов
make test

# Полная проверка (линтинг + тесты)
make check
```

## Настройка IDE

### VS Code
Рекомендуемые расширения (.vscode/extensions.json):
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.mypy-type-checker",
    "charliermarsh.ruff",
    "ms-python.black-formatter"
  ]
}
```

### PyCharm
1. Установите плагин Ruff
2. Настройте Black как форматтер кода
3. Включите проверку типов MyPy

## CI/CD Pipeline

Проект автоматически проверяется в GitHub Actions:
- ✅ Линтинг с Ruff
- ✅ Форматирование с Black
- ✅ Проверка типов с MyPy  
- ✅ Проверка безопасности с Bandit
- ✅ Проверка уязвимостей с Safety
- ✅ Запуск тестов с покрытием кода

## Структура тестов

```
tests/
├── conftest.py           # Общие фикстуры
├── test_api.py          # Тесты API endpoints
├── test_nlp_service.py  # Тесты NLP сервиса
└── integration/         # Интеграционные тесты
    ├── test_telegram.py
    └── test_wildberries.py
```

## Покрытие кода

Цель - поддержание покрытия кода на уровне 80%+. Используйте pytest-cov для мониторинга покрытия.