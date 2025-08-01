# 🤝 Вклад в проект

Спасибо за интерес к проекту Easy Flow! Мы приветствуем вклад от сообщества.

## Как начать

### 1. Подготовка окружения
```bash
# Форкните репозиторий на GitHub
git clone https://github.com/your-username/easy-flow.git
cd easy-flow

# Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установите зависимости
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Установите pre-commit хуки
pre-commit install
```

### 2. Запуск проекта
```bash
# Запустите базу данных и Redis
docker-compose up -d postgres redis

# Запустите приложение
uvicorn main:app --reload
```

## Процесс разработки

### 1. Создание ветки
```bash
# Создайте ветку для вашей функции
git checkout -b feature/amazing-feature

# Или для исправления ошибки
git checkout -b fix/bug-description
```

### 2. Разработка
- Следуйте существующему стилю кода
- Добавляйте тесты для новой функциональности
- Обновляйте документацию при необходимости
- Убедитесь, что все тесты проходят

### 3. Проверка качества кода
```bash
# Запустите все проверки
make check

# Или по отдельности
make lint      # Проверка стиля кода
make format    # Форматирование кода
make test      # Запуск тестов
make security  # Проверка безопасности
```

### 4. Коммит и push
```bash
# Зафиксируйте изменения
git add .
git commit -m "feat: add amazing feature"

# Отправьте в ваш форк
git push origin feature/amazing-feature
```

### 5. Pull Request
1. Откройте Pull Request на GitHub
2. Опишите ваши изменения
3. Дождитесь review от мейнтейнеров
4. Внесите правки если необходимо

## Стандарты кода

### Соглашения по именованию
- **Переменные и функции**: snake_case
- **Классы**: PascalCase
- **Константы**: UPPER_SNAKE_CASE
- **Файлы**: snake_case.py

### Структура коммитов
Используйте [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

<body>

<footer>
```

**Типы коммитов:**
- `feat`: новая функция
- `fix`: исправление ошибки
- `docs`: изменения в документации
- `style`: форматирование кода
- `refactor`: рефакторинг
- `test`: добавление тестов
- `chore`: изменения в сборке или инструментах

**Примеры:**
```
feat(api): add conversation history endpoint
fix(telegram): handle empty messages correctly
docs(readme): update installation instructions
```

### Документация кода
```python
def process_message(message: str, user_id: str) -> dict:
    """
    Обрабатывает сообщение пользователя и генерирует ответ.
    
    Args:
        message: Текст сообщения от пользователя
        user_id: Уникальный идентификатор пользователя
        
    Returns:
        dict: Словарь с ответом и метаданными
        
    Raises:
        ValueError: Если сообщение пустое
        APIError: Если AI сервис недоступен
    """
    if not message.strip():
        raise ValueError("Сообщение не может быть пустым")
    
    # Реализация...
```

## Тестирование

### Типы тестов
- **Unit тесты** - тестирование отдельных функций
- **Integration тесты** - тестирование взаимодействий
- **E2E тесты** - полный цикл использования

### Написание тестов
```python
import pytest
from app.services.ai_service import AIService

class TestAIService:
    @pytest.fixture
    def ai_service(self):
        return AIService(api_key="test-key")
    
    async def test_generate_response(self, ai_service):
        """Тест генерации ответа AI."""
        response = await ai_service.generate_response(
            message="Привет",
            user_id="test-user"
        )
        
        assert response is not None
        assert isinstance(response, dict)
        assert "text" in response
        assert len(response["text"]) > 0
    
    async def test_empty_message_raises_error(self, ai_service):
        """Тест обработки пустого сообщения."""
        with pytest.raises(ValueError):
            await ai_service.generate_response("", "test-user")
```

### Запуск тестов
```bash
# Все тесты
pytest

# Конкретный файл
pytest tests/test_ai_service.py

# С покрытием кода
pytest --cov=app tests/

# Только быстрые тесты
pytest -m "not slow"
```

## Добавление новых интеграций

### 1. Структура интеграции
```python
# app/services/integrations/new_platform.py
from typing import Dict, Any
from app.services.integrations.base import BaseIntegration

class NewPlatformIntegration(BaseIntegration):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def send_message(self, user_id: str, message: str) -> bool:
        """Отправка сообщения пользователю."""
        # Реализация отправки
        pass
    
    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка входящего webhook."""
        # Реализация обработки
        pass
```

### 2. Добавление роутов
```python
# app/api/routes/integrations/new_platform.py
from fastapi import APIRouter, Depends
from app.services.integrations.new_platform import NewPlatformIntegration

router = APIRouter(prefix="/new-platform", tags=["new-platform"])

@router.post("/webhook")
async def handle_webhook(
    payload: dict,
    integration: NewPlatformIntegration = Depends(get_new_platform_integration)
):
    return await integration.handle_webhook(payload)
```

### 3. Конфигурация
```python
# app/core/config.py
class Settings:
    # Добавьте новые переменные окружения
    NEW_PLATFORM_API_KEY: str = ""
    NEW_PLATFORM_WEBHOOK_SECRET: str = ""
```

### 4. Тесты
```python
# tests/integrations/test_new_platform.py
import pytest
from app.services.integrations.new_platform import NewPlatformIntegration

class TestNewPlatformIntegration:
    @pytest.fixture
    def integration(self):
        return NewPlatformIntegration(api_key="test-key")
    
    async def test_send_message(self, integration):
        # Тест отправки сообщения
        pass
    
    async def test_handle_webhook(self, integration):
        # Тест обработки webhook
        pass
```

### 5. Документация
Добавьте документацию в `docs/integrations/new_platform.md`

## Сообщения об ошибках

### Хорошие баг-репорты содержат:
1. **Описание проблемы** - что происходит
2. **Ожидаемое поведение** - что должно происходить
3. **Шаги воспроизведения** - как повторить ошибку
4. **Окружение** - версия Python, ОС, и т.д.
5. **Логи** - релевантные сообщения об ошибках

### Шаблон issue
```markdown
## Описание проблемы
Краткое описание проблемы.

## Воспроизведение
1. Перейдите на...
2. Кликните на...
3. Увидите ошибку...

## Ожидаемое поведение
Описание ожидаемого результата.

## Окружение
- Python версия: 3.11
- ОС: Ubuntu 22.04
- Версия easy-flow: 1.0.0

## Дополнительная информация
Логи, скриншоты, и т.д.
```

## Предложения функций

### Хорошие предложения содержат:
1. **Проблему** - какую проблему решает функция
2. **Решение** - как функция должна работать
3. **Альтернативы** - рассмотренные варианты
4. **Примеры** - как будет использоваться

## Кодекс поведения

### Наши стандарты
- Уважительное общение
- Конструктивная критика
- Фокус на улучшении проекта
- Помощь новичкам

### Недопустимо
- Оскорбления и личные атаки
- Дискриминация любого вида
- Спам и офф-топик
- Публикация чужой личной информации

## Контакты

- **GitHub Issues**: [Создать issue](https://github.com/evgenygurin/easy-flow/issues)
- **Discussions**: [GitHub Discussions](https://github.com/evgenygurin/easy-flow/discussions)
- **Email**: dev@easy-flow.ru

Спасибо за вклад в проект! 🚀