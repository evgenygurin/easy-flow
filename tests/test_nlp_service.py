"""
Тесты для NLP сервиса.
"""
import pytest

from app.services.nlp_service import NLPService


@pytest.fixture
def nlp_service():
    """Экземпляр NLP сервиса для тестов."""
    return NLPService()


@pytest.mark.asyncio
async def test_process_greeting_message(nlp_service: NLPService):
    """Тест обработки приветствия."""
    result = await nlp_service.process_message(
        message="Привет! Как дела?",
        user_id="test_user"
    )

    assert result.intent == "greeting"
    assert result.language == "ru"
    assert result.confidence > 0.0


@pytest.mark.asyncio
async def test_process_order_status_message(nlp_service: NLPService):
    """Тест обработки запроса статуса заказа."""
    result = await nlp_service.process_message(
        message="Где мой заказ №12345?",
        user_id="test_user"
    )

    assert result.intent == "order_inquiry"
    assert result.entities is not None
    assert "order_number" in result.entities
    assert result.entities["order_number"] == "12345"


@pytest.mark.asyncio
async def test_process_complaint_message(nlp_service: NLPService):
    """Тест обработки жалобы."""
    result = await nlp_service.process_message(
        message="Я недоволен качеством товара, хочу подать жалобу",
        user_id="test_user"
    )

    assert result.intent == "complaint"
    assert result.sentiment == "negative"


@pytest.mark.asyncio
async def test_extract_entities_with_amount(nlp_service: NLPService):
    """Тест извлечения сущностей с суммой."""
    result = await nlp_service.process_message(
        message="Верните мне 1500 рублей за заказ №999",
        user_id="test_user"
    )

    assert result.entities is not None
    assert "amount" in result.entities
    assert result.entities["amount"] == 1500.0
    assert "order_number" in result.entities
    assert result.entities["order_number"] == "999"


@pytest.mark.asyncio
async def test_extract_email_entity(nlp_service: NLPService):
    """Тест извлечения email."""
    result = await nlp_service.process_message(
        message="Мой email: test@example.com",
        user_id="test_user"
    )

    assert result.entities is not None
    assert "email" in result.entities
    assert result.entities["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_detect_language_russian(nlp_service: NLPService):
    """Тест определения русского языка."""
    result = await nlp_service.process_message(
        message="Здравствуйте, у меня проблема с товаром",
        user_id="test_user"
    )

    assert result.language == "ru"


@pytest.mark.asyncio
async def test_detect_language_english(nlp_service: NLPService):
    """Тест определения английского языка."""
    result = await nlp_service.process_message(
        message="Hello, I have a problem with my order",
        user_id="test_user"
    )

    assert result.language == "en"


@pytest.mark.asyncio
async def test_sentiment_positive(nlp_service: NLPService):
    """Тест положительного настроения."""
    result = await nlp_service.process_message(
        message="Спасибо большое! Всё отлично получил заказ!",
        user_id="test_user"
    )

    assert result.sentiment == "positive"


@pytest.mark.asyncio
async def test_sentiment_negative(nlp_service: NLPService):
    """Тест отрицательного настроения."""
    result = await nlp_service.process_message(
        message="Ужасное качество! Всё сломано! Верните деньги!",
        user_id="test_user"
    )

    assert result.sentiment == "negative"


@pytest.mark.asyncio
async def test_unknown_intent(nlp_service: NLPService):
    """Тест обработки неизвестного намерения."""
    result = await nlp_service.process_message(
        message="абракадабра xyz 123",
        user_id="test_user"
    )

    # Должно либо не найти намерение, либо иметь низкую уверенность
    assert result.intent is None or result.confidence < 0.5
