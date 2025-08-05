"""
Конфигурация для тестов.
"""
import uuid
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.services.ai_service import AIService
from app.services.conversation_service import ConversationService
from app.services.integration_service import IntegrationService
from app.services.nlp_service import NLPService


@pytest.fixture
def client():
    """Тестовый клиент FastAPI."""
    return TestClient(app)


@pytest.fixture
def mock_conversation_service():
    """Мок сервиса диалогов."""
    service = Mock(spec=ConversationService)
    return service


@pytest.fixture
def mock_nlp_service():
    """Мок NLP сервиса."""
    service = Mock(spec=NLPService)
    return service


@pytest.fixture
def mock_ai_service():
    """Мок AI сервиса."""
    service = Mock(spec=AIService)
    return service


@pytest.fixture
def mock_integration_service():
    """Мок сервиса интеграций."""
    service = Mock(spec=IntegrationService)
    return service


@pytest.fixture
def sample_user_id():
    """Тестовый ID пользователя."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_session_id():
    """Тестовый ID сессии."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_message():
    """Тестовое сообщение."""
    return "Привет! Как дела с моим заказом №12345?"


@pytest.fixture
def sample_chat_request(sample_user_id, sample_session_id, sample_message):
    """Тестовый запрос для чата."""
    return {
        "message": sample_message,
        "user_id": sample_user_id,
        "session_id": sample_session_id,
        "platform": "web"
    }
