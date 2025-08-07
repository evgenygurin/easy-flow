"""Основное FastAPI приложение для AI платформы поддержки клиентов."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import get_conversation_service, get_integration_service, get_messaging_service
from app.api.routes import conversation, health, integration, messaging
from app.core.config import settings
from app.services.conversation_service import ConversationService
from app.services.integration_service import IntegrationService
from app.services.messaging_service import MessagingService
from app.services.nlp_service import NLPService
from app.services.repository_service import repository_service


logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # Startup
    logger.info("Запуск AI Customer Support Platform")
    
    # Initialize database tables
    if repository_service.available:
        await repository_service.create_tables()
        logger.info("Database tables initialized")
    else:
        logger.warning("Repository service not available - running without database")

    # Настройка dependency injection
    app.dependency_overrides[ConversationService] = get_conversation_service
    app.dependency_overrides[IntegrationService] = get_integration_service
    app.dependency_overrides[MessagingService] = get_messaging_service
    app.dependency_overrides[NLPService] = get_nlp_service

    yield

    # Shutdown
    logger.info("Остановка AI Customer Support Platform")
    if repository_service.available:
        await repository_service.close()
        logger.info("Database connections closed")


# Создаем FastAPI приложение
app = FastAPI(
    title="AI Customer Support Platform",
    description="Универсальная AI платформа для поддержки клиентов в e-commerce",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency Injection factories
def get_nlp_service() -> NLPService:
    """Factory для NLPService."""
    return NLPService()

# Подключение роутеров
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(conversation.router, prefix="/api/v1/conversation", tags=["conversation"])
app.include_router(integration.router, prefix="/api/v1/integration", tags=["integration"])
app.include_router(messaging.router, tags=["messaging"])

@app.get("/")
async def root() -> dict[str, str]:
    """Корневой endpoint."""
    return {
        "message": "AI Customer Support Platform API",
        "version": "0.1.0",
        "status": "running"
    }
