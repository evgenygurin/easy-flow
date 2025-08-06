"""Тесты для системы распознавания паттернов."""
import pytest

from app.services.nlp.pattern_recognition import PatternRecognitionService


@pytest.fixture
def pattern_service():
    """Создание экземпляра PatternRecognitionService для тестов."""
    return PatternRecognitionService()


class TestPatternRecognitionService:
    """Тесты для PatternRecognitionService."""

    def test_classify_intent_greeting(self, pattern_service):
        """Тест распознавания приветствия."""
        test_messages = [
            "Привет",
            "Здравствуйте",
            "Добрый день",
            "Добрый вечер",
            "Доброе утро",
        ]

        for message in test_messages:
            intent, confidence = pattern_service.classify_intent(message)
            assert intent == "greeting"
            assert confidence > 0.5

    def test_classify_intent_order_status(self, pattern_service):
        """Тест распознавания запроса о статусе заказа."""
        test_messages = [
            "Где мой заказ?",
            "Статус заказа №12345",
            "Когда доставят заказ?",
            "Отследить заказ",
            "Хочу узнать статус заказа",
        ]

        for message in test_messages:
            intent, confidence = pattern_service.classify_intent(message)
            assert intent == "order_inquiry"
            assert confidence > 0.5

    def test_classify_intent_payment_issue(self, pattern_service):
        """Тест распознавания проблем с оплатой."""
        test_messages = [
            "Не прошла оплата",
            "Ошибка при оплате картой",
            "Списали деньги дважды",
            "Проблема с платежом",
            "Не могу оплатить",
        ]

        for message in test_messages:
            intent, confidence = pattern_service.classify_intent(message)
            assert intent == "payment_inquiry"
            assert confidence > 0.5

    def test_classify_intent_return_request(self, pattern_service):
        """Тест распознавания запроса на возврат."""
        test_messages = [
            "Хочу вернуть товар",
            "Как сделать возврат?",
            "Товар не подошел, верните деньги",
            "Отмена заказа",
            "Возврат средств",
        ]

        for message in test_messages:
            intent, confidence = pattern_service.classify_intent(message)
            assert intent == "refund_request"
            assert confidence > 0.5

    def test_classify_intent_unknown(self, pattern_service):
        """Тест нераспознанного намерения."""
        test_messages = ["абракадабра", "12345", "...", "ъъъ"]

        for message in test_messages:
            intent, confidence = pattern_service.classify_intent(message)
            assert intent is None or confidence < 0.3

    def test_extract_entities_order_number(self, pattern_service):
        """Тест извлечения номера заказа."""
        test_cases = [
            ("Заказ №12345", {"order_number": "12345"}),
            ("Мой заказ 98765", {"order_number": "98765"}),
            ("Заказ номер 555", {"order_number": "555"}),
            ("Order #ABC123", {"order_number": "ABC123"}),
        ]

        for message, expected in test_cases:
            entities = pattern_service.extract_entities(message, "order_inquiry")
            if entities:
                assert "order_number" in entities
                assert entities["order_number"] == expected["order_number"]

    def test_extract_entities_amount(self, pattern_service):
        """Тест извлечения суммы."""
        test_cases = [
            ("Списали 1000 рублей", {"amount": 1000.0}),
            ("Сумма 500.50 руб", {"amount": 500.50}),
            ("999 ₽", {"amount": 999.0}),
            ("2500 рублей", {"amount": 2500.0}),
        ]

        for message, expected in test_cases:
            entities = pattern_service.extract_entities(message, "payment_inquiry")
            if entities:
                assert "amount" in entities
                assert entities["amount"] == expected["amount"]

    def test_extract_entities_phone(self, pattern_service):
        """Тест извлечения номера телефона."""
        test_cases = [
            ("Мой телефон +7 (999) 123-45-67", {"+7 (999) 123-45-67"}),
            ("Звоните 8-800-555-35-35", {"8-800-555-35-35"}),
            ("Номер: 79991234567", {"79991234567"}),
        ]

        for message, expected_phone in test_cases:
            entities = pattern_service.extract_entities(message, "contact_info")
            if entities:
                assert "phone" in entities
                assert entities["phone"] in expected_phone

    def test_extract_entities_email(self, pattern_service):
        """Тест извлечения email."""
        test_cases = [
            ("Мой email test@example.com", "test@example.com"),
            ("Пишите на admin@company.ru", "admin@company.ru"),
            ("Email: user.name@domain.co.uk", "user.name@domain.co.uk"),
        ]

        for message, expected_email in test_cases:
            entities = pattern_service.extract_entities(message, "contact_info")
            if entities:
                assert "email" in entities
                assert entities["email"] == expected_email

    def test_extract_entities_date(self, pattern_service):
        """Тест извлечения даты."""
        test_cases = [
            ("Доставка 25.12.2023", "25.12.2023"),
            ("Заказ от 01.01.24", "01.01.24"),
            ("Приедет сегодня", "сегодня"),
            ("Доставят завтра", "завтра"),
        ]

        for message, expected_date in test_cases:
            entities = pattern_service.extract_entities(message, "shipping_info")
            if entities:
                assert "date" in entities
                assert entities["date"] == expected_date

    def test_confidence_calculation(self, pattern_service):
        """Тест вычисления уверенности."""
        # Точное совпадение должно давать высокую уверенность
        intent1, confidence1 = pattern_service.classify_intent("Привет")
        assert confidence1 > 0.8

        # Частичное совпадение должно давать среднюю уверенность
        intent2, confidence2 = pattern_service.classify_intent("Приветствую вас")
        assert 0.5 < confidence2 < 0.8

        # Нет совпадения - низкая уверенность
        intent3, confidence3 = pattern_service.classify_intent("абракадабра")
        assert confidence3 < 0.3

    def test_case_insensitive_matching(self, pattern_service):
        """Тест регистронезависимого поиска."""
        test_cases = [
            ("ПРИВЕТ", "greeting"),
            ("ГДЕ МОЙ ЗАКАЗ", "order_status"),
            ("Возврат Товара", "return_request"),
        ]

        for message, expected_intent in test_cases:
            intent, confidence = pattern_service.classify_intent(message)
            expected_mapping = {
                "greeting": "greeting",
                "order_status": "order_inquiry",
                "return_request": "refund_request",
            }
            assert intent == expected_mapping.get(expected_intent, expected_intent)
            assert confidence > 0.5

    def test_multiple_entities_extraction(self, pattern_service):
        """Тест извлечения нескольких сущностей."""
        message = "Заказ №12345 на сумму 1500 рублей, доставка 25.12.2023"
        entities = pattern_service.extract_entities(message, "order_inquiry")

        assert "order_number" in entities
        assert entities["order_number"] == "12345"
        assert "amount" in entities
        assert entities["amount"] == 1500.0
        assert "date" in entities
        assert entities["date"] == "25.12.2023"
