"""Repository service that provides access to all repositories."""
import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.database import Base
from app.repositories.interfaces.conversation_repository import ConversationRepository
from app.repositories.interfaces.integration_repository import IntegrationRepository
from app.repositories.interfaces.knowledge_base_repository import KnowledgeBaseRepository
from app.repositories.interfaces.message_repository import MessageRepository
from app.repositories.interfaces.user_repository import UserRepository
from app.repositories.repository_factory import SQLAlchemyRepositoryFactory
from app.services.service_factory import ServiceFactory


logger = structlog.get_logger()


class RepositoryService:
    """Service that manages database connections and provides repository access."""

    def __init__(self) -> None:
        if settings.DATABASE_URL:
            # Async engine for main operations
            self.async_engine = create_async_engine(
                settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://'),
                echo=False,
                pool_size=20,
                max_overflow=30,
                pool_pre_ping=True,
                pool_recycle=3600
            )

            self.async_session_maker = async_sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            # Sync engine for migrations and administrative tasks
            self.sync_engine = create_engine(
                settings.DATABASE_URL,
                echo=False,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True
            )

            self.sync_session_maker = sessionmaker(self.sync_engine)

            # Repository factory
            self._repository_factory = SQLAlchemyRepositoryFactory(self.async_session_maker)
            
            # Service factory
            self._service_factory = ServiceFactory(self._repository_factory)

            self._available = True
            logger.info("Repository service initialized", url=settings.DATABASE_URL.split('@')[-1])
        else:
            self.async_engine = None
            self.async_session_maker = None
            self.sync_engine = None
            self.sync_session_maker = None
            self._repository_factory = None
            self._service_factory = None
            self._available = False
            logger.warning("DATABASE_URL not configured, repository service unavailable")

    @property
    def available(self) -> bool:
        """Check if repository service is available."""
        return self._available

    # Repository access methods
    
    def get_user_repository(self) -> UserRepository:
        """Get user repository instance."""
        if not self._repository_factory:
            raise RuntimeError("Repository service not available")
        return self._repository_factory.create_user_repository()

    def get_conversation_repository(self) -> ConversationRepository:
        """Get conversation repository instance."""
        if not self._repository_factory:
            raise RuntimeError("Repository service not available")
        return self._repository_factory.create_conversation_repository()

    def get_message_repository(self) -> MessageRepository:
        """Get message repository instance."""
        if not self._repository_factory:
            raise RuntimeError("Repository service not available")
        return self._repository_factory.create_message_repository()

    def get_integration_repository(self) -> IntegrationRepository:
        """Get integration repository instance."""
        if not self._repository_factory:
            raise RuntimeError("Repository service not available")
        return self._repository_factory.create_integration_repository()

    def get_knowledge_base_repository(self) -> KnowledgeBaseRepository:
        """Get knowledge base repository instance."""
        if not self._repository_factory:
            raise RuntimeError("Repository service not available")
        return self._repository_factory.create_knowledge_base_repository()

    # Service access methods
    
    def get_service_factory(self) -> ServiceFactory:
        """Get service factory instance."""
        if not self._service_factory:
            raise RuntimeError("Repository service not available")
        return self._service_factory

    # Database management methods

    async def create_tables(self) -> bool:
        """Create tables in database."""
        if not self._available:
            return False

        try:
            async with self.async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created")
            return True
        except Exception as e:
            logger.error("Error creating tables", error=str(e))
            return False

    async def health_check(self) -> bool:
        """Check database health."""
        if not self._available:
            return False

        try:
            async with self.async_session_maker() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error("Database unavailable", error=str(e))
            return False

    async def close(self) -> None:
        """Close database connections."""
        if self.async_engine:
            await self.async_engine.dispose()
        if self.sync_engine:
            self.sync_engine.dispose()
        logger.info("Database connections closed")


# Global repository service instance
repository_service = RepositoryService()