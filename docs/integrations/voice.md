# 🎙️ Голосовые ассистенты

## Поддерживаемые платформы

### Yandex Alice
Российский голосовой помощник

**Настройка:**
```bash
YANDEX_ALICE_SKILL_ID=your-skill-id
YANDEX_ALICE_TOKEN=your-oauth-token
```

**Возможности:**
- Навыки для Алисы
- Голосовое взаимодействие
- Интеграция с умным домом
- Поддержка русского языка

### Amazon Alexa
Международный стандарт голосовых ассистентов

**Настройка:**
```bash
ALEXA_SKILL_ID=your-skill-id
ALEXA_CLIENT_SECRET=your-client-secret
```

**Возможности:**
- Custom Skills
- Smart Home интеграция
- Многоязычная поддержка
- Rich audio responses

### Google Assistant
Голосовой помощник от Google

**Настройка:**
```bash
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_CLIENT_EMAIL=your-service-account@project.iam.gserviceaccount.com
```

**Возможности:**
- Actions on Google
- Rich responses
- Интеграция с Google Services
- Conversational AI

### Apple Siri
Голосовой помощник Apple

**Настройка:**
```bash
SIRI_SHORTCUTS_TOKEN=your-shortcuts-token
APPLE_TEAM_ID=your-team-id
```

**Возможности:**
- Siri Shortcuts
- SiriKit интеграция
- iOS/macOS поддержка
- Intent handling

## Обработка голосовых команд

### Получение интентов
```http
POST /api/v1/integration/webhook/alice
Content-Type: application/json

{
  "request": {
    "command": "где мой заказ",
    "type": "SimpleUtterance"
  },
  "session": {
    "user_id": "user123"
  }
}
```

### Ответ голосового ассистента
```json
{
  "response": {
    "text": "Ваш заказ №12345 находится в пути",
    "tts": "Ваш заказ номер двенадцать тысяч триста сорок пять находится в пути",
    "end_session": false
  }
}
```

## Типы взаимодействий

### Информационные запросы
- Статус заказа
- Информация о товарах  
- Часы работы поддержки
- Контактная информация

### Транзакционные операции
- Оформление заказа
- Отмена заказа
- Изменение адреса доставки
- Обратная связь

### Навигационные команды
- Поиск товаров
- Переход к категориям
- Помощь и инструкции
- Настройки аккаунта

## Настройка навыков/скиллов

### Yandex Alice
1. Зарегистрируйтесь в Яндекс.Диалогах
2. Создайте новый навык
3. Настройте webhook URL
4. Опубликуйте навык

### Amazon Alexa
1. Создайте аккаунт разработчика Amazon
2. Создайте новый Alexa Skill
3. Настройте Interaction Model
4. Подключите endpoint

### Google Assistant
1. Создайте проект в Actions Console
2. Настройте Conversational Actions
3. Определите интенты и entities
4. Развертывание через Cloud Functions

## Обработка контекста

Голосовые ассистенты поддерживают:
- Многоходовые диалоги
- Сохранение контекста сессии
- Персонализация ответов
- Интеграция с историей заказов

## Аналитика голосовых взаимодействий

Метрики:
- Частота использования команд
- Успешность распознавания
- Время сессий
- Конверсия в действия