"""
Тесты для сервиса векторных представлений.
"""
import numpy as np
import pytest

from app.services.embeddings_service import embeddings_service


@pytest.fixture
def embeddings_service_instance():
    """Возвращаем мок сервиса для тестирования."""
    # Используем глобальный мок из conftest.py
    return embeddings_service


async def test_encode_text(embeddings_service_instance):
    """Тест создания embedding для текста."""
    text = "Тестовый текст"
    embedding = await embeddings_service_instance.encode_text(text)

    assert embedding is not None
    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (5,)  # Размерность должна соответствовать нашему моку в conftest.py


async def test_calculate_similarity(embeddings_service_instance):
    """Тест расчета сходства между embeddings."""
    embedding1 = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)
    embedding2 = np.array([0.2, 0.3, 0.4, 0.5, 0.6], dtype=np.float32)

    similarity = embeddings_service_instance.calculate_similarity(embedding1, embedding2)
    assert 0 <= similarity <= 1


async def test_search_similar_knowledge(embeddings_service_instance):
    """Тест поиска похожих элементов в базе знаний."""
    query_text = "Тестовый запрос"

    # Создаем тестовый набор данных
    knowledge_embeddings = {
        "id1": np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32),
        "id2": np.array([0.2, 0.3, 0.4, 0.5, 0.6], dtype=np.float32)
    }

    knowledge_items = {
        "id1": {"id": "id1", "title": "Документ 1", "content": "Содержание документа 1"},
        "id2": {"id": "id2", "title": "Документ 2", "content": "Содержание документа 2"}
    }

    results = await embeddings_service_instance.search_similar_knowledge(
        query_text, knowledge_embeddings, knowledge_items
    )

    assert isinstance(results, list)
    assert len(results) <= 3  # top_k=3 по умолчанию


async def test_get_embedding_stats(embeddings_service_instance):
    """Тест получения статистики модели embeddings."""
    stats = embeddings_service_instance.get_embedding_stats()

    assert isinstance(stats, dict)
    assert stats["available"] is True
    assert stats["model_name"] == "intfloat/multilingual-e5-large"
    assert stats["embedding_dimension"] == 5  # Размерность должна соответствовать моку
