"""Тесты для AI сервиса."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.conversation import MessageResponse, MessageType, Platform
from app.services.ai_service import AIResponse, AIService


@pytest.fixture
def ai_service():
    """Фикстура AI сервиса."""
    with patch('app.services.ai_service.embeddings_service'), \
         patch('app.services.ai_service.cache_service'):
        service = AIService()
        return service


@pytest.fixture
def sample_conversation_history():
    """Фикстура с историей диалога."""
    return [
        MessageResponse(
            id="1",
            content="Привет",
            message_type=MessageType.USER,
            user_id="user1",
            session_id="session1",
            platform=Platform.WEB,
            created_at="2024-01-01T10:00:00"
        ),
        MessageResponse(
            id="2",
            content="Здравствуйте! Как дела?",
            message_type=MessageType.ASSISTANT,
            user_id="user1",
            session_id="session1",
            platform=Platform.WEB,
            created_at="2024-01-01T10:00:05"
        )
    ]


class TestAIService:
    """Тесты для AI сервиса."""

    @pytest.mark.asyncio
    async def test_generate_response_template_match(self, ai_service):
        """Тест генерации ответа по шаблону."""
        with patch.object(ai_service, '_generate_template_response', return_value="Шаблонный ответ"), \
             patch('app.services.ai_service.cache_service.get_ai_response_cache', return_value=None), \
             patch('app.services.ai_service.cache_service.set_ai_response_cache', return_value=True):

            response = await ai_service.generate_response(
                message="Привет",
                intent="greeting"
            )

            assert isinstance(response, AIResponse)
            assert response.response == "Шаблонный ответ"
            assert response.confidence == 0.9

    @pytest.mark.asyncio
    async def test_generate_response_cached(self, ai_service):
        """Тест использования кэшированного ответа."""
        cached_response = {
            "response": "Кэшированный ответ",
            "confidence": 0.95,
            "suggested_actions": ["action1"],
            "next_questions": ["question1"]
        }

        with patch('app.services.ai_service.cache_service.get_ai_response_cache', return_value=cached_response):
            response = await ai_service.generate_response(
                message="Тестовое сообщение",
                intent="test"
            )

            assert response.response == "Кэшированный ответ"
            assert response.confidence == 0.95

    @pytest.mark.asyncio
    async def test_generate_response_knowledge_base(self, ai_service):
        """Тест поиска в базе знаний."""
        with patch('app.services.ai_service.cache_service.get_ai_response_cache', return_value=None), \
             patch.object(ai_service, '_search_knowledge_base_embeddings', return_value=None), \
             patch.object(ai_service, '_search_knowledge_base', return_value="Ответ из базы знаний"), \
             patch('app.services.ai_service.cache_service.set_ai_response_cache', return_value=True):

            response = await ai_service.generate_response(
                message="Сколько стоит доставка?",
                intent="shipping_info"
            )

            assert response.response == "Ответ из базы знаний"
            assert response.confidence == 0.8

    @pytest.mark.asyncio
    async def test_generate_response_openai_fallback(self, ai_service):
        """Тест использования OpenAI как fallback."""
        mock_openai_response = AIResponse(
            response="OpenAI ответ",
            confidence=0.85,
            suggested_actions=["action"],
            next_questions=["question"]
        )

        with patch('app.services.ai_service.cache_service.get_ai_response_cache', return_value=None), \
             patch.object(ai_service, '_search_knowledge_base_embeddings', return_value=None), \
             patch.object(ai_service, '_search_knowledge_base', return_value=None), \
             patch.object(ai_service, '_generate_llm_response', return_value=mock_openai_response), \
             patch('app.services.ai_service.cache_service.set_ai_response_cache', return_value=True):

            response = await ai_service.generate_response(
                message="Сложный вопрос",
                intent="complex_query"
            )

            assert response.response == "OpenAI ответ"
            assert response.confidence == 0.85

    @pytest.mark.asyncio
    async def test_generate_response_error_fallback(self, ai_service):
        """Тест fallback при ошибке."""
        with patch('app.services.ai_service.cache_service.get_ai_response_cache', side_effect=Exception("Cache error")):
            response = await ai_service.generate_response(
                message="Тестовое сообщение",
                intent="test"
            )

            assert "Извините, я не совсем понял" in response.response
            assert response.confidence == 0.3

    def test_generate_template_response_with_entities(self, ai_service):
        """Тест генерации шаблонного ответа с подстановкой сущностей."""
        entities = {"order_number": "12345"}
        response = ai_service._generate_template_response("order_status", entities)

        # Проверяем, что номер заказа подставился в шаблон
        assert "12345" in response

    def test_generate_template_response_no_entities(self, ai_service):
        """Тест генерации шаблонного ответа без сущностей."""
        response = ai_service._generate_template_response("greeting")

        assert "Здравствуйте!" in response
        assert "AI-помощник" in response

    def test_search_knowledge_base_found(self, ai_service):
        """Тест поиска в базе знаний с найденным результатом."""
        message = "время доставки"
        response = ai_service._search_knowledge_base(message, None)

        assert response is not None
        assert "доставка занимает" in response

    def test_search_knowledge_base_not_found(self, ai_service):
        """Тест поиска в базе знаний без результата."""
        message = "несуществующий запрос xyz"
        response = ai_service._search_knowledge_base(message, None)

        assert response is None

    def test_build_system_prompt_with_intent(self, ai_service):
        """Тест построения системного промпта с намерением."""
        prompt = ai_service._build_system_prompt("complaint")

        assert "AI помощник для службы поддержки" in prompt
        assert "жалобу" in prompt
        assert "сочувствующим" in prompt

    def test_build_system_prompt_without_intent(self, ai_service):
        """Тест построения системного промпта без намерения."""
        prompt = ai_service._build_system_prompt(None)

        assert "AI помощник для службы поддержки" in prompt
        # Не должно быть специфичной для намерения информации
        assert "жалобу" not in prompt

    def test_build_user_prompt_full_context(self, ai_service, sample_conversation_history):
        """Тест построения пользовательского промпта с полным контекстом."""
        message = "Какой статус моего заказа?"
        entities = {"order_number": "12345"}

        prompt = ai_service._build_user_prompt(message, entities, sample_conversation_history)

        assert message in prompt
        assert "12345" in prompt
        assert "Предыдущий контекст диалога" in prompt
        assert "Привет" in prompt

    def test_build_user_prompt_minimal(self, ai_service):
        """Тест построения минимального пользовательского промпта."""
        message = "Простой вопрос"

        prompt = ai_service._build_user_prompt(message, None, None)

        assert message in prompt
        assert "Извлеченная информация" not in prompt
        assert "Предыдущий контекст" not in prompt

    def test_get_suggested_actions_known_intent(self, ai_service):
        """Тест получения предлагаемых действий для известного намерения."""
        actions = ai_service._get_suggested_actions("order_status")

        assert len(actions) > 0
        assert "Проверить статус заказа" in actions

    def test_get_suggested_actions_unknown_intent(self, ai_service):
        """Тест получения предлагаемых действий для неизвестного намерения."""
        actions = ai_service._get_suggested_actions("unknown_intent")

        assert actions == []

    def test_get_next_questions_known_intent(self, ai_service):
        """Тест получения следующих вопросов для известного намерения."""
        questions = ai_service._get_next_questions("order_status")

        assert len(questions) > 0
        assert any("заказ" in q.lower() for q in questions)

    def test_get_next_questions_unknown_intent(self, ai_service):
        """Тест получения следующих вопросов для неизвестного намерения."""
        questions = ai_service._get_next_questions("unknown_intent")

        assert questions == []

    def test_generate_fallback_response_known_intent(self, ai_service):
        """Тест генерации fallback ответа для известного намерения."""
        response = ai_service._generate_fallback_response("greeting", "Привет")

        assert "Здравствуйте" in response

    def test_generate_fallback_response_unknown_intent(self, ai_service):
        """Тест генерации fallback ответа для неизвестного намерения."""
        response = ai_service._generate_fallback_response("unknown", "Что-то непонятное")

        assert "готов помочь" in response

    @pytest.mark.asyncio
    async def test_call_openai_api_success(self, ai_service):
        """Тест успешного вызова OpenAI API."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "OpenAI ответ"
        mock_response.choices[0].finish_reason = "stop"

        ai_service._openai_client = MagicMock()
        ai_service._openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        response = await ai_service._call_openai_api("System prompt", "User prompt", "greeting")

        assert response.response == "OpenAI ответ"
        assert response.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_call_openai_api_error(self, ai_service):
        """Тест ошибки при вызове OpenAI API."""
        ai_service._openai_client = MagicMock()
        ai_service._openai_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

        with pytest.raises(Exception, match="API Error"):
            await ai_service._call_openai_api("System prompt", "User prompt", "greeting")


@pytest.mark.asyncio
async def test_ai_service_integration():
    """Интеграционный тест AI сервиса."""
    with patch('app.services.ai_service.embeddings_service'), \
         patch('app.services.ai_service.cache_service.get_ai_response_cache', return_value=None), \
         patch('app.services.ai_service.cache_service.set_ai_response_cache', return_value=True):

        service = AIService()

        # Тест простого приветствия (должен использовать шаблон)
        response = await service.generate_response("Привет", "greeting")
        assert "Здравствуйте" in response.response
        assert response.confidence == 0.9

        # Тест вопроса о доставке (должен найти в базе знаний)
        response = await service.generate_response("Сколько времени доставка?", "shipping_info")
        assert "доставка занимает" in response.response
        assert response.confidence == 0.8
