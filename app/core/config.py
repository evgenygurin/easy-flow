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

    # Адаптер безопасности и шифрования
    ENCRYPTION_KEY: str | None = None
    
    # Российские e-commerce платформы (Phase 1)
    # Wildberries
    WILDBERRIES_API_KEY: str | None = None
    WILDBERRIES_JWT_SECRET: str | None = None
    
    # Ozon
    OZON_CLIENT_ID: str | None = None
    OZON_API_KEY: str | None = None
    OZON_CHAT_API_TOKEN: str | None = None
    
    # 1C-Bitrix
    BITRIX_WEBHOOK_URL: str | None = None
    BITRIX_CLIENT_ID: str | None = None
    BITRIX_CLIENT_SECRET: str | None = None
    BITRIX_ACCESS_TOKEN: str | None = None
    BITRIX_REFRESH_TOKEN: str | None = None
    
    # InSales
    INSALES_API_KEY: str | None = None
    INSALES_API_PASSWORD: str | None = None
    INSALES_SHOP_DOMAIN: str | None = None
    INSALES_WEBHOOK_SECRET: str | None = None
    
    # Международные e-commerce платформы (Phase 2)
    # Shopify
    SHOPIFY_ACCESS_TOKEN: str | None = None
    SHOPIFY_SHOP_DOMAIN: str | None = None
    SHOPIFY_API_VERSION: str = "2023-10"
    SHOPIFY_WEBHOOK_SECRET: str | None = None
    
    # WooCommerce
    WOOCOMMERCE_CONSUMER_KEY: str | None = None
    WOOCOMMERCE_CONSUMER_SECRET: str | None = None
    WOOCOMMERCE_SITE_URL: str | None = None
    WOOCOMMERCE_API_VERSION: str = "v3"
    WOOCOMMERCE_WEBHOOK_SECRET: str | None = None
    
    # BigCommerce
    BIGCOMMERCE_STORE_HASH: str | None = None
    BIGCOMMERCE_ACCESS_TOKEN: str | None = None
    BIGCOMMERCE_CLIENT_ID: str | None = None
    BIGCOMMERCE_WEBHOOK_SECRET: str | None = None
    
    # Magento
    MAGENTO_BASE_URL: str | None = None
    MAGENTO_ADMIN_TOKEN: str | None = None
    MAGENTO_API_VERSION: str = "V1"
    MAGENTO_WEBHOOK_SECRET: str | None = None

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
