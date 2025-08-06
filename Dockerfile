# Используем официальный образ Python 3.12
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости и uv
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

# Добавляем uv в PATH
ENV PATH="/root/.cargo/bin:$PATH"

# Копируем файлы конфигурации
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости через uv
RUN uv sync --frozen

# Копируем код приложения
COPY . .

# Создаем непривилегированного пользователя
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

# Открываем порт
EXPOSE 8000

# Команда для запуска приложения
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]