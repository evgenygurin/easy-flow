"""Repository factory for dependency injection and management."""
from typing import Protocol

from app.repositories.interfaces.conversation_repository import ConversationRepository
from app.repositories.interfaces.integration_repository import IntegrationRepository
from app.repositories.interfaces.knowledge_base_repository import KnowledgeBaseRepository
from app.repositories.interfaces.message_repository import MessageRepository
from app.repositories.interfaces.user_repository import UserRepository
from app.repositories.sqlalchemy.conversation_repository import SQLAlchemyConversationRepository
from app.repositories.sqlalchemy.integration_repository import SQLAlchemyIntegrationRepository
from app.repositories.sqlalchemy.knowledge_base_repository import SQLAlchemyKnowledgeBaseRepository
from app.repositories.sqlalchemy.message_repository import SQLAlchemyMessageRepository
from app.repositories.sqlalchemy.user_repository import SQLAlchemyUserRepository


class RepositoryFactory(Protocol):
    """Protocol for repository factory."""

    def create_user_repository(self) -> UserRepository:
        """Create user repository instance."""
        ...

    def create_conversation_repository(self) -> ConversationRepository:
        """Create conversation repository instance."""
        ...

    def create_message_repository(self) -> MessageRepository:
        """Create message repository instance."""
        ...

    def create_integration_repository(self) -> IntegrationRepository:
        """Create integration repository instance."""
        ...

    def create_knowledge_base_repository(self) -> KnowledgeBaseRepository:
        """Create knowledge base repository instance."""
        ...


class SQLAlchemyRepositoryFactory:
    """SQLAlchemy implementation of repository factory."""

    def __init__(self, session_factory) -> None:
        """Initialize with session factory.
        
        Args:
        ----
            session_factory: SQLAlchemy async session factory
            
        """
        self.session_factory = session_factory

    def create_user_repository(self) -> UserRepository:
        """Create user repository instance."""
        return SQLAlchemyUserRepository(self.session_factory)

    def create_conversation_repository(self) -> ConversationRepository:
        """Create conversation repository instance."""
        return SQLAlchemyConversationRepository(self.session_factory)

    def create_message_repository(self) -> MessageRepository:
        """Create message repository instance."""
        return SQLAlchemyMessageRepository(self.session_factory)

    def create_integration_repository(self) -> IntegrationRepository:
        """Create integration repository instance."""
        return SQLAlchemyIntegrationRepository(self.session_factory)

    def create_knowledge_base_repository(self) -> KnowledgeBaseRepository:
        """Create knowledge base repository instance."""
        return SQLAlchemyKnowledgeBaseRepository(self.session_factory)