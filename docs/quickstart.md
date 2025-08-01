# 🚀 Быстрый старт

## Предварительные требования
- Python 3.11+
- Docker и Docker Compose
- PostgreSQL 15+
- Redis 7+

## Установка

### 1. Клонируйте репозиторий
```bash
git clone https://github.com/evgenygurin/easy-flow.git
cd easy-flow
```

### 2. Настройте окружение
```bash
cp .env.example .env
# Отредактируйте .env файл с вашими API ключами
```

### 3. Запустите с Docker Compose
```bash
docker-compose up -d
```

### 4. Или локально
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## Первоначальная настройка

API будет доступно по адресу: http://localhost:8000

- **Документация API**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc  
- **Health Check**: http://localhost:8000/health/

## Следующие шаги

- Ознакомьтесь с [конфигурацией](configuration.md) для настройки интеграций
- Изучите [API документацию](api.md) для начала работы
- Настройте [интеграции](integrations/) с вашими платформами