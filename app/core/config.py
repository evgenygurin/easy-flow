"""Конфигурация приложения для AI платформы поддержки клиентов."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Основные настройки приложения."""

    # Основные настройки
    APP_NAME: str = "AI Customer Support Platform"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # API настройки
    API_V1_STR: str = "/api/v1"
    ALLOWED_HOSTS: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])

    # База данных
    DATABASE_URL: str | None = None
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI сервисы
    OPENAI_API_KEY: str | None = None
    YANDEX_GPT_API_KEY: str | None = None
    YANDEX_CLOUD_FOLDER_ID: str | None = None

    # Yandex Alice
    ALICE_SKILL_ID: str | None = None
    ALICE_OAUTH_TOKEN: str | None = None

    # Безопасность
    SECRET_KEY: str = Field(default="dev-secret-key", env="SECRET_KEY", description="Секретный ключ для JWT токенов")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Интеграции e-commerce
    WILDBERRIES_API_KEY: str | None = None
    OZON_API_KEY: str | None = None
    BITRIX_WEBHOOK_URL: str | None = None

    # Платежи
    YOOKASSA_SHOP_ID: str | None = None
    YOOKASSA_SECRET_KEY: str | None = None

    # Мессенджеры
    TELEGRAM_BOT_TOKEN: str | None = None
    VK_ACCESS_TOKEN: str | None = None
    WHATSAPP_ACCESS_TOKEN: str | None = None

    # Логирование
    LOG_LEVEL: str = "INFO"

    class Config:
        """Конфигурация настроек."""

        env_file = ".env"
        case_sensitive = True


# Глобальный объект настроек
settings = Settings()
