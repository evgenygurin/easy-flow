"""FastAPI dependency providers for services."""
from app.services.conversation_service import ConversationService
from app.services.integration_service import IntegrationService
from app.services.repository_service import repository_service


def get_conversation_service() -> ConversationService:
    """Get conversation service instance with repository dependencies."""
    if not repository_service.available:
        raise RuntimeError("Repository service not available")
    
    service_factory = repository_service.get_service_factory()
    return service_factory.create_conversation_service()


def get_integration_service() -> IntegrationService:
    """Get integration service instance with repository dependencies."""
    if not repository_service.available:
        raise RuntimeError("Repository service not available")
    
    service_factory = repository_service.get_service_factory()
    return service_factory.create_integration_service()