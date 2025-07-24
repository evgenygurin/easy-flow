"""
Сервис для обработки естественного языка (NLP).
"""
from typing import Optional, Dict, Any, List
import re
import structlog
from datetime import datetime

from app.models.conversation import NLPResult
from app.core.config import settings

logger = structlog.get_logger()


class NLPService:
    """Сервис для обработки естественного языка."""
    
    def __init__(self):
        # TODO: Инициализация моделей NLP
        self._intent_patterns = self._load_intent_patterns()
        self._entity_patterns = self._load_entity_patterns()
    
    async def process_message(
        self,
        message: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> NLPResult:
        """
        Обработка сообщения через NLP.
        
        Args:
            message: Текст сообщения
            user_id: ID пользователя
            context: Дополнительный контекст
            
        Returns:
            NLPResult: Результат обработки NLP
        """
        try:
            logger.info(
                "Обработка сообщения через NLP",
                user_id=user_id,
                message_length=len(message)
            )
            
            # Очистка и нормализация текста
            normalized_message = self._normalize_text(message)
            
            # Определение языка
            language = self._detect_language(normalized_message)
            
            # Распознавание намерений
            intent, confidence = self._classify_intent(normalized_message)
            
            # Извлечение сущностей
            entities = self._extract_entities(normalized_message, intent)
            
            # Анализ эмоциональной окраски
            sentiment = self._analyze_sentiment(normalized_message)
            
            result = NLPResult(
                intent=intent,
                entities=entities,
                confidence=confidence,
                sentiment=sentiment,
                language=language
            )
            
            logger.info(
                "NLP обработка завершена",
                intent=intent,
                confidence=confidence,
                entities_count=len(entities) if entities else 0
            )
            
            return result
            
        except Exception as e:
            logger.error("Ошибка обработки NLP", error=str(e), user_id=user_id)
            # Возвращаем базовый результат при ошибке
            return NLPResult(
                intent="unknown",
                confidence=0.0,
                language="ru"
            )
    
    def _normalize_text(self, text: str) -> str:
        """Нормализация текста."""
        # Удаляем лишние пробелы
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Приводим к нижнему регистру
        text = text.lower()
        
        # Удаляем специальные символы (кроме знаков препинания)
        text = re.sub(r'[^\w\s\.,!?-]', '', text)
        
        return text
    
    def _detect_language(self, text: str) -> str:
        """Определение языка сообщения."""
        # Простая эвристика для определения русского языка
        russian_chars = re.findall(r'[а-яё]', text)
        english_chars = re.findall(r'[a-z]', text)
        
        if len(russian_chars) > len(english_chars):
            return "ru"
        elif len(english_chars) > 0:
            return "en"
        else:
            return "ru"  # по умолчанию русский
    
    def _classify_intent(self, text: str) -> tuple[Optional[str], float]:
        """Классификация намерений."""
        max_confidence = 0.0
        detected_intent = None
        
        for intent, patterns in self._intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    confidence = self._calculate_pattern_confidence(pattern, text)
                    if confidence > max_confidence:
                        max_confidence = confidence
                        detected_intent = intent
        
        return detected_intent, max_confidence
    
    def _extract_entities(self, text: str, intent: Optional[str]) -> Optional[Dict[str, Any]]:
        """Извлечение именованных сущностей."""
        entities = {}
        
        # Извлечение номеров заказов
        order_matches = re.findall(r'заказ[а-я]*\s*№?\s*(\d+)', text)
        if order_matches:
            entities['order_number'] = order_matches[0]
        
        # Извлечение номеров товаров/артикулов
        product_matches = re.findall(r'(?:товар|артикул)[а-я]*\s*№?\s*([a-zA-Z0-9-]+)', text)
        if product_matches:
            entities['product_id'] = product_matches[0]
        
        # Извлечение сумм
        amount_matches = re.findall(r'(\d+(?:\.\d{2})?)\s*(?:руб|₽|рублей)', text)
        if amount_matches:
            entities['amount'] = float(amount_matches[0])
        
        # Извлечение дат
        date_patterns = [
            r'(\d{1,2}\.\d{1,2}\.\d{4})',
            r'(\d{1,2}\.\d{1,2}\.\d{2})',
            r'(сегодня|вчера|завтра)'
        ]
        for pattern in date_patterns:
            dates = re.findall(pattern, text)
            if dates:
                entities['date'] = dates[0]
                break
        
        # Извлечение email
        email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if email_matches:
            entities['email'] = email_matches[0]
        
        # Извлечение телефонов
        phone_matches = re.findall(r'[\+]?[7-8][\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}', text)
        if phone_matches:
            entities['phone'] = phone_matches[0]
        
        return entities if entities else None
    
    def _analyze_sentiment(self, text: str) -> str:
        """Анализ эмоциональной окраски."""
        # Простой анализ на основе ключевых слов
        positive_words = [
            'спасибо', 'отлично', 'хорошо', 'замечательно', 'прекрасно', 
            'доволен', 'рад', 'нравится', 'супер', 'круто'
        ]
        
        negative_words = [
            'плохо', 'ужасно', 'не работает', 'проблема', 'ошибка', 
            'жалоба', 'недоволен', 'не нравится', 'верните', 'возврат'
        ]
        
        neutral_words = [
            'информация', 'как', 'где', 'когда', 'сколько', 'можно', 'подскажите'
        ]
        
        positive_score = sum(1 for word in positive_words if word in text)
        negative_score = sum(1 for word in negative_words if word in text)
        neutral_score = sum(1 for word in neutral_words if word in text)
        
        if negative_score > positive_score and negative_score > neutral_score:
            return "negative"
        elif positive_score > negative_score and positive_score > neutral_score:
            return "positive"
        else:
            return "neutral"
    
    def _calculate_pattern_confidence(self, pattern: str, text: str) -> float:
        """Вычисление уверенности для паттерна."""
        # Простая метрика на основе длины совпадения
        matches = re.findall(pattern, text, re.IGNORECASE)
        if not matches:
            return 0.0
        
        # Чем больше символов в совпадении, тем выше уверенность
        max_match_length = max(len(str(match)) for match in matches)
        confidence = min(0.9, max_match_length / 20.0)  # Нормализуем до 0.9
        
        return confidence
    
    def _load_intent_patterns(self) -> Dict[str, List[str]]:
        """Загрузка паттернов для определения намерений."""
        return {
            "greeting": [
                r"привет", r"здравствуйте", r"добрый день", r"добрый вечер", 
                r"доброе утро", r"добро пожаловать", r"хай", r"hello"
            ],
            "order_status": [
                r"статус заказа", r"где мой заказ", r"когда доставят", 
                r"отследить заказ", r"заказ №\s*\d+", r"трек номер"
            ],
            "product_info": [
                r"информация о товаре", r"характеристики", r"описание товара",
                r"есть ли в наличии", r"сколько стоит", r"цена"
            ],
            "complaint": [
                r"жалоба", r"претензия", r"недоволен", r"возмущен", 
                r"плохое качество", r"не работает", r"брак"
            ],
            "refund_request": [
                r"возврат", r"верните деньги", r"отмена заказа", 
                r"не подошел", r"вернуть товар"
            ],
            "payment_issue": [
                r"не прошел платеж", r"ошибка оплаты", r"списали деньги",
                r"проблема с картой", r"возврат средств"
            ],
            "shipping_info": [
                r"доставка", r"когда привезут", r"стоимость доставки",
                r"способы доставки", r"курьер"
            ],
            "technical_support": [
                r"не работает сайт", r"ошибка", r"не могу войти",
                r"технические проблемы", r"баг"
            ],
            "goodbye": [
                r"до свидания", r"пока", r"спасибо", r"всего хорошего", r"bye"
            ]
        }
    
    def _load_entity_patterns(self) -> Dict[str, str]:
        """Загрузка паттернов для извлечения сущностей."""
        return {
            "order_number": r"(?:заказ|order)[а-я]*\s*№?\s*(\d+)",
            "product_id": r"(?:товар|артикул|product)[а-я]*\s*№?\s*([a-zA-Z0-9-]+)",
            "amount": r"(\d+(?:\.\d{2})?)\s*(?:руб|₽|рублей|dollars?)",
            "date": r"(\d{1,2}\.\d{1,2}\.\d{4})",
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "phone": r"[\+]?[7-8][\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
        }