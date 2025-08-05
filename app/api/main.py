"""Основное FastAPI приложение для AI платформы поддержки клиентов."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import conversation, health, integration
from app.core.config import settings
from app.services.conversation_service import ConversationService
from app.services.nlp_service import NLPService


logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    # Startup
    logger.info("Запуск AI Customer Support Platform")

    # Настройка dependency injection
    app.dependency_overrides[ConversationService] = get_conversation_service
    app.dependency_overrides[NLPService] = get_nlp_service

    yield

    # Shutdown
    logger.info("Остановка AI Customer Support Platform")


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
def get_conversation_service() -> ConversationService:
    """Factory для ConversationService."""
    return ConversationService()

def get_nlp_service() -> NLPService:
    """Factory для NLPService."""
    return NLPService()

# Подключение роутеров
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(conversation.router, prefix="/api/v1/conversation", tags=["conversation"])
app.include_router(integration.router, prefix="/api/v1/integration", tags=["integration"])

@app.get("/")
async def root() -> dict[str, str]:
    """Корневой endpoint."""
    return {
        "message": "AI Customer Support Platform API",
        "version": "0.1.0",
        "status": "running"
    }
