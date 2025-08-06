"""FastAPI dependency providers for services and controllers."""
from app.api.controllers.conversation_controller import ConversationController
from app.api.controllers.integration_controller import IntegrationController
from app.services.conversation_service import ConversationService
from app.services.integration_service import IntegrationService
from app.services.nlp_service import NLPService
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


def get_nlp_service() -> NLPService:
    """Get NLP service instance."""
    return NLPService()


# Controller dependencies
def get_conversation_controller() -> ConversationController:
    """Get conversation controller instance with service dependencies."""
    return ConversationController(
        conversation_service=get_conversation_service(),
        nlp_service=get_nlp_service()
    )


def get_integration_controller() -> IntegrationController:
    """Get integration controller instance with service dependencies."""
    return IntegrationController(
        integration_service=get_integration_service()
    )