"""
Конфигурация для тестов.
"""
import uuid
from unittest.mock import MagicMock, Mock, patch

import numpy as np
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
    # Настраиваем моки методов AI сервиса
    async def mock_generate_response(*args, **kwargs):
        return "Это тестовый ответ от AI сервиса"

    service.generate_response.side_effect = mock_generate_response

    async def mock_analyze_intent(*args, **kwargs):
        return {"intent": "test_intent", "confidence": 0.95}

    service.analyze_intent.side_effect = mock_analyze_intent
    return service


# Глобальный мок для AI сервиса
@pytest.fixture(autouse=True)
def mock_global_ai_service():
    """Глобальный мок AI сервиса."""
    with patch('app.services.ai_service.AIService', autospec=True) as mock_class:
        mock_instance = MagicMock(spec=AIService)

        async def mock_generate_response(*args, **kwargs):
            return "Это тестовый ответ от AI сервиса"

        mock_instance.generate_response.side_effect = mock_generate_response

        async def mock_analyze_intent(*args, **kwargs):
            return {"intent": "test_intent", "confidence": 0.95}

        mock_instance.analyze_intent.side_effect = mock_analyze_intent

        mock_class.return_value = mock_instance
        yield mock_class


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


# Мок для SentenceTransformer, чтобы не загружать модель во время тестов
@pytest.fixture(autouse=True)
def mock_sentence_transformer():
    """Мок для SentenceTransformer."""
    with patch('sentence_transformers.SentenceTransformer') as mock:
        # Настраиваем мок для возврата фиктивных embeddings
        mock_instance = MagicMock()
        mock_instance.encode.return_value = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)
        mock_instance.get_sentence_embedding_dimension.return_value = 5
        mock.return_value = mock_instance
        yield mock


# Полный мок для сервиса embeddings_service
@pytest.fixture(autouse=True)
def mock_embeddings_service():
    """Мок для сервиса embeddings."""
    with patch('app.services.embeddings_service.embeddings_service') as mock_service:
        # Настраиваем свойства и методы
        mock_service._available = True
        mock_service.model = MagicMock()

        # Моки методов
        async def mock_encode_text(text):
            return np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)

        mock_service.encode_text = mock_encode_text

        def mock_calculate_similarity(embedding1, embedding2):
            return 0.85  # Фиксированное значение для предсказуемости

        mock_service.calculate_similarity = mock_calculate_similarity

        async def mock_search_similar_knowledge(query_text, knowledge_embeddings, knowledge_items, threshold=0.6, top_k=3):
            return [{"id": "test-id", "title": "Test Document", "content": "Test content", "similarity_score": 0.85}]

        mock_service.search_similar_knowledge = mock_search_similar_knowledge

        def mock_get_embedding_stats():
            return {
                "available": True,
                "model_name": "mock-model",
                "embedding_dimension": 5,
                "max_seq_length": 512
            }

        mock_service.get_embedding_stats = mock_get_embedding_stats

        async def mock_encode_knowledge_base(knowledge_items):
            return {item["id"]: np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32) for item in knowledge_items}

        mock_service.encode_knowledge_base = mock_encode_knowledge_base

        async def mock_create_knowledge_base_index(knowledge_base):
            embeddings_dict = {item["id"]: np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32) for item in knowledge_base}
            items_dict = {item["id"]: item for item in knowledge_base}
            return embeddings_dict, items_dict

        mock_service.create_knowledge_base_index = mock_create_knowledge_base_index

        yield mock_service


# Мок для Redis кэша
@pytest.fixture(autouse=True)
def mock_redis_cache():
    """Мок для Redis кэша."""
    with patch('app.services.cache_service.cache_service', autospec=True) as mock:
        mock._available = True
        mock._redis = MagicMock()
        mock._redis.get.return_value = None
        yield mock
