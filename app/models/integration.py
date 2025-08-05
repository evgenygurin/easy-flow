"""Модели данных для интеграций с внешними платформами."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PlatformInfo(BaseModel):
    """Информация о подключенной платформе."""

    platform_id: str
    platform_name: str
    status: str
    connected_at: datetime
    last_sync: datetime | None = None
    configuration: dict[str, Any]


class WebhookPayload(BaseModel):
    """Входящий webhook от внешней платформы."""

    platform: str = Field(..., description="Название платформы")
    event_type: str = Field(..., description="Тип события")
    data: dict[str, Any] = Field(..., description="Данные события")
    timestamp: datetime | None = Field(None, description="Время события")
    signature: str | None = Field(None, description="Подпись для проверки")


class IntegrationRequest(BaseModel):
    """Запрос на подключение интеграции."""

    platform: str = Field(..., description="Название платформы")
    credentials: dict[str, str] = Field(..., description="Данные для подключения")
    configuration: dict[str, Any] | None = Field(None, description="Дополнительные настройки")


class IntegrationResult(BaseModel):
    """Результат интеграции."""

    platform_id: str = Field(..., description="ID платформы")
    success: bool = Field(default=True, description="Успешность операции")
    message: str = Field(default="success", description="Сообщение о результате")
    data: dict[str, Any] | None = Field(None, description="Дополнительные данные")
    timestamp: datetime = Field(default_factory=datetime.now, description="Время выполнения")


class WebhookConfig(BaseModel):
    """Конфигурация webhook для платформы."""

    platform: str = Field(..., description="Название платформы")
    url: str = Field(..., description="URL webhook")
    secret: str | None = Field(None, description="Секретный ключ")
    events: list[str] = Field(..., description="Типы событий")
    active: bool = Field(True, description="Активность webhook")
