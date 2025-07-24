"""
Основное FastAPI приложение для AI платформы поддержки клиентов.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import structlog

from app.core.config import settings
from app.api.routes import conversation, health, integration

logger = structlog.get_logger()

# Создаем FastAPI приложение
app = FastAPI(
    title="AI Customer Support Platform",
    description="Универсальная AI платформа для поддержки клиентов в e-commerce",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(conversation.router, prefix="/api/v1/conversation", tags=["conversation"])
app.include_router(integration.router, prefix="/api/v1/integration", tags=["integration"])

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске приложения."""
    logger.info("Запуск AI Customer Support Platform")

@app.on_event("shutdown") 
async def shutdown_event():
    """Очистка ресурсов при остановке приложения."""
    logger.info("Остановка AI Customer Support Platform")

@app.get("/")
async def root() -> Dict[str, str]:
    """Корневой endpoint."""
    return {
        "message": "AI Customer Support Platform API",
        "version": "0.1.0",
        "status": "running"
    }