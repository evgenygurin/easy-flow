"""Система распознавания паттернов для NLP."""
import re
from typing import Any

import structlog


logger = structlog.get_logger()


class PatternRecognitionService:
    """Сервис для распознавания паттернов в тексте."""

    def __init__(self):
        self.logger = logger.bind(service="pattern_recognition")

        # Загружаем паттерны
        self.intent_patterns = self._load_intent_patterns()
        self.entity_patterns = self._load_entity_patterns()
        self.product_patterns = self._load_product_patterns()
        self.name_patterns = self._load_name_patterns()

    def classify_intent(self, text: str) -> tuple[str | None, float]:
        """Классификация интента на основе паттернов.

        Args:
        ----
            text: Входной текст

        Returns:
        -------
            Tuple[Optional[str], float]: (интент, уверенность)
        """
        try:
            text_lower = text.lower().strip()

            # Проверяем каждый интент
            for intent, patterns in self.intent_patterns.items():
                for pattern in patterns:
                    if isinstance(pattern, str):
                        # Простое вхождение подстроки
                        if pattern in text_lower:
                            confidence = self._calculate_confidence(text_lower, pattern)
                            return intent, confidence
                    else:
                        # Регулярное выражение
                        if re.search(pattern, text_lower, re.IGNORECASE):
                            confidence = self._calculate_regex_confidence(text_lower, pattern)
                            return intent, confidence

            return None, 0.0

        except Exception as e:
            self.logger.error("Ошибка классификации интента", error=str(e))
            return None, 0.0

    def extract_entities(self, text: str, intent: str | None = None) -> dict[str, Any]:
        """Извлечение сущностей из текста.

        Args:
        ----
            text: Входной текст
            intent: Интент для контекстного извлечения

        Returns:
        -------
            Dict[str, Any]: Словарь извлеченных сущностей
        """
        try:
            entities = {}

            # Базовые сущности
            entities.update(self._extract_base_entities(text))

            # Продукты
            products = self._extract_products(text)
            if products:
                entities["products"] = products

            # Имена
            names = self._extract_names(text)
            if names:
                entities["names"] = names

            # Контекстные сущности на основе интента
            if intent:
                context_entities = self._extract_context_entities(text, intent)
                entities.update(context_entities)

            return entities

        except Exception as e:
            self.logger.error("Ошибка извлечения сущностей", error=str(e))
            return {}

    def _extract_base_entities(self, text: str) -> dict[str, Any]:
        """Извлечение базовых сущностей."""
        entities = {}
        text_lower = text.lower()

        # Проверяем каждую категорию сущностей
        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                if isinstance(pattern, str):
                    if pattern in text_lower:
                        entities[entity_type] = True
                        break
                else:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        if match.groups():
                            entities[entity_type] = match.group(1)
                        else:
                            entities[entity_type] = True
                        break

        return entities

    def _extract_products(self, text: str) -> list[str]:
        """Извлечение названий продуктов."""
        products = []
        text_lower = text.lower()

        for _category, product_list in self.product_patterns.items():
            for product in product_list:
                if product in text_lower:
                    products.append(product)

        return list(set(products))  # Убираем дубликаты

    def _extract_names(self, text: str) -> list[str]:
        """Извлечение имен."""
        names = []

        # Ищем имена в начале предложений или после обращений
        name_contexts = [
            r'меня зовут\s+(\w+)',
            r'я\s+(\w+)',
            r'имя\s+(\w+)',
            r'^(\w+)[\s,]',  # Имя в начале
        ]

        for pattern in name_contexts:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                potential_name = match.group(1)
                if self._is_valid_name(potential_name):
                    names.append(potential_name)

        # Проверяем по словарю имен
        words = text.split()
        for word in words:
            clean_word = re.sub(r'[^\w]', '', word)
            if self._is_known_name(clean_word):
                names.append(clean_word)

        return list(set(names))

    def _extract_context_entities(self, text: str, intent: str) -> dict[str, Any]:
        """Извлечение контекстных сущностей на основе интента."""
        entities = {}

        if intent == "order_inquiry":
            # Ищем номера заказов
            order_patterns = [
                r'\b(\d{6,12})\b',  # 6-12 цифр
                r'[№#]\s*(\d+)',     # № или # с цифрами
                r'заказ\s*(\d+)',    # "заказ 123456"
            ]

            for pattern in order_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    entities["order_number"] = match.group(1)
                    break

        elif intent == "payment_inquiry":
            # Ищем суммы
            amount_patterns = [
                r'(\d+)\s*руб',
                r'(\d+)\s*₽',
                r'(\d+)\s*рублей',
                r'(\d+)\s*тысяч',
            ]

            for pattern in amount_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    entities["amount"] = match.group(1)
                    break

        elif intent == "shipping_inquiry":
            # Ищем адреса
            address_patterns = [
                r'г\.\s*([^\s,]+)',  # г. Москва
                r'ул\.\s*([^,\d]+)',  # ул. Ленина
                r'д\.\s*(\d+)',  # д. 10
            ]

            address_parts = {}
            for pattern in address_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    if 'г.' in pattern:
                        address_parts['city'] = match.group(1)
                    elif 'ул.' in pattern:
                        address_parts['street'] = match.group(1)
                    elif 'д.' in pattern:
                        address_parts['house'] = match.group(1)

            if address_parts:
                entities["address"] = address_parts

        return entities

    def _calculate_confidence(self, text: str, pattern: str) -> float:
        """Расчет уверенности для простого паттерна."""
        # Базовая уверенность
        base_confidence = 0.7

        # Увеличиваем уверенность если паттерн встречается несколько раз
        occurrences = text.count(pattern)
        if occurrences > 1:
            base_confidence += 0.1 * (occurrences - 1)

        # Увеличиваем уверенность если паттерн в начале предложения
        if text.strip().startswith(pattern):
            base_confidence += 0.1

        # Длина паттерна относительно текста
        if len(pattern) / len(text) > 0.1:
            base_confidence += 0.1

        return min(base_confidence, 1.0)

    def _calculate_regex_confidence(self, text: str, pattern) -> float:
        """Расчет уверенности для regex паттерна."""
        # Более высокая базовая уверенность для regex
        base_confidence = 0.8

        # Находим все совпадения
        matches = list(re.finditer(pattern, text, re.IGNORECASE))

        if len(matches) > 1:
            base_confidence += 0.1

        # Проверяем качество совпадения
        for match in matches:
            match_length = len(match.group(0))
            if match_length > 5:  # Длинное совпадение
                base_confidence += 0.05

        return min(base_confidence, 1.0)

    def _is_valid_name(self, word: str) -> bool:
        """Проверка, является ли слово валидным именем."""
        # Базовые проверки
        if len(word) < 2 or len(word) > 20:
            return False

        if not word.isalpha():
            return False

        # Не должно быть частыми словами
        common_words = {
            'я', 'ты', 'он', 'она', 'мы', 'вы', 'они',
            'да', 'нет', 'как', 'что', 'где', 'когда',
            'хочу', 'могу', 'буду', 'есть', 'был', 'была'
        }

        if word.lower() in common_words:
            return False

        return True

    def _is_known_name(self, word: str) -> bool:
        """Проверка по словарю известных имен."""
        # Проверяем по загруженным паттернам имен
        return word.lower() in self.name_patterns.get('names', [])

    def _load_intent_patterns(self) -> dict[str, list]:
        """Загрузка паттернов интентов."""
        return {
            "greeting": [
                "привет", "здравствуй", "добро пожаловать", "приветствую",
                "добрый день", "добрый вечер", "доброе утро", "хай", "hi"
            ],

            "order_inquiry": [
                "заказ", "заказать", "купить", "оформить", "приобрести",
                "статус заказа", "где заказ", "мой заказ", "проверить заказ"
            ],

            "payment_inquiry": [
                "оплата", "заплатить", "карта", "платеж", "счет", "оплачу",
                "как оплатить", "способы оплаты", "банковская карта"
            ],

            "shipping_inquiry": [
                "доставка", "доставить", "когда получу", "адрес", "курьер",
                "отследить", "посылка", "время доставки", "где посылка"
            ],

            "complaint": [
                "жалоба", "проблема", "не работает", "плохо", "ужасно",
                "недоволен", "возмущен", "безобразие", "негодую"
            ],

            "refund_request": [
                "возврат", "вернуть деньги", "отменить", "не подходит",
                "не нравится", "верните", "хочу вернуть"
            ],

            "help": [
                "помощь", "помоги", "не понимаю", "объясни", "расскажи",
                "что делать", "как быть", "подскажи"
            ],

            "goodbye": [
                "пока", "до свидания", "прощай", "увидимся", "досвидос",
                "бай", "bye", "until", "спасибо за помощь"
            ]
        }

    def _load_entity_patterns(self) -> dict[str, list]:
        """Загрузка паттернов сущностей."""
        return {
            "yes": [
                "да", "конечно", "определенно", "безусловно", "точно",
                "ага", "угу", "ок", "хорошо", "согласен", "yes"
            ],

            "no": [
                "нет", "не", "никак", "ни в коем случае", "отказываюсь",
                "не хочу", "не буду", "no", "нope"
            ],

            "when": [
                "когда", "во сколько", "в какое время", "какого числа",
                "when", "what time"
            ],

            "where": [
                "где", "куда", "откуда", "в каком месте", "where"
            ],

            "how": [
                "как", "каким образом", "каким способом", "how"
            ],

            "phone": [
                re.compile(r'\+?[78][\s-]?\(?(\d{3})\)?[\s-]?(\d{3})[\s-]?(\d{2})[\s-]?(\d{2})'),
                re.compile(r'\d{3}-\d{3}-\d{2}-\d{2}')
            ],

            "email": [
                re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
            ],

            "number": [
                re.compile(r'\b\d+\b')
            ]
        }

    def _load_product_patterns(self) -> dict[str, list[str]]:
        """Загрузка паттернов продуктов."""
        return {
            "electronics": [
                "телефон", "смартфон", "планшет", "ноутбук", "компьютер",
                "наушники", "колонки", "зарядка", "провод", "кабель",
                "телевизор", "монитор", "клавиатура", "мышь"
            ],

            "clothing": [
                "футболка", "рубашка", "джинсы", "брюки", "юбка",
                "платье", "куртка", "пальто", "свитер", "кофта",
                "обувь", "кроссовки", "ботинки", "туфли", "сапоги"
            ],

            "books": [
                "книга", "роман", "учебник", "словарь", "энциклопедия",
                "художественная литература", "детектив", "фантастика"
            ],

            "home": [
                "мебель", "стол", "стул", "кровать", "шкаф", "диван",
                "посуда", "тарелка", "чашка", "кастрюля", "сковорода",
                "декор", "ваза", "картина", "подушка", "одеяло"
            ],

            "beauty": [
                "косметика", "крем", "шампунь", "мыло", "духи",
                "помада", "тушь", "тональный крем", "лак для ногтей"
            ]
        }

    def _load_name_patterns(self) -> dict[str, list[str]]:
        """Загрузка паттернов имен."""
        return {
            "names": [
                # Мужские имена
                "александр", "алексей", "андрей", "антон", "артем",
                "владимир", "дмитрий", "евгений", "иван", "максим",
                "михаил", "николай", "олег", "павел", "роман",
                "сергей", "юрий", "ярослав",

                # Женские имена
                "александра", "алина", "анастасия", "анна", "валерия",
                "виктория", "дарья", "елена", "екатерина", "ирина",
                "ксения", "мария", "наталья", "ольга", "светлана",
                "татьяна", "юлия"
            ]
        }
