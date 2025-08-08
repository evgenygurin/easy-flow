"""Service factory for dependency injection."""
from app.repositories.repository_factory import RepositoryFactory
from app.services.conversation_service import ConversationService
from app.services.integration_service import IntegrationService
from app.services.messaging_service import MessagingService
from app.services.voice_service import VoiceService


class ServiceFactory:
    """Factory for creating service instances with proper dependency injection."""

    def __init__(self, repository_factory: RepositoryFactory) -> None:
        """Initialize service factory with repository factory.
        
        Args:
        ----
            repository_factory: Factory for creating repository instances
            
        """
        self.repository_factory = repository_factory

    def create_conversation_service(self) -> ConversationService:
        """Create conversation service with repository dependencies."""
        return ConversationService(
            user_repository=self.repository_factory.create_user_repository(),
            conversation_repository=self.repository_factory.create_conversation_repository(),
            message_repository=self.repository_factory.create_message_repository()
        )

    def create_integration_service(self) -> IntegrationService:
        """Create integration service with repository dependencies."""
        return IntegrationService(
            integration_repository=self.repository_factory.create_integration_repository()
        )

    def create_messaging_service(self) -> MessagingService:
        """Create messaging service with repository dependencies."""
        return MessagingService(
            integration_repository=self.repository_factory.create_integration_repository()
        )

    def create_voice_service(self) -> VoiceService:
        """Create voice service with repository dependencies."""
        return VoiceService(
            integration_repository=self.repository_factory.create_integration_repository()
        )