"""
Конфигурация приложения для AI платформы поддержки клиентов.
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Основные настройки приложения."""
    
    # Основные настройки
    APP_NAME: str = "AI Customer Support Platform"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # API настройки
    API_V1_STR: str = "/api/v1"
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # База данных
    DATABASE_URL: Optional[str] = None
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # AI сервисы
    OPENAI_API_KEY: Optional[str] = None
    YANDEX_GPT_API_KEY: Optional[str] = None
    YANDEX_CLOUD_FOLDER_ID: Optional[str] = None
    
    # Yandex Alice
    ALICE_SKILL_ID: Optional[str] = None
    ALICE_OAUTH_TOKEN: Optional[str] = None
    
    # Безопасность
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Интеграции e-commerce
    WILDBERRIES_API_KEY: Optional[str] = None
    OZON_API_KEY: Optional[str] = None
    BITRIX_WEBHOOK_URL: Optional[str] = None
    
    # Платежи
    YOOKASSA_SHOP_ID: Optional[str] = None
    YOOKASSA_SECRET_KEY: Optional[str] = None
    
    # Мессенджеры
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    VK_ACCESS_TOKEN: Optional[str] = None
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    
    # Логирование
    LOG_LEVEL: str = "INFO"
    
    class Config:
        """Конфигурация настроек."""
        env_file = ".env"
        case_sensitive = True


# Глобальный объект настроек
settings = Settings()