# 🚀 Быстрая настройка Gemini AI Assistant

## ✅ Чек-лист настройки

### 1. API ключ Google Gemini

- [ ] Перейти на [Google AI Studio](https://makersuite.google.com/)
- [ ] Создать API ключ (начинается с `AIza...`)
- [ ] Скопировать ключ

### 2. Настройка GitHub секретов

- [ ] Открыть `Settings` → `Secrets and variables` → `Actions`
- [ ] Добавить `New repository secret`
- [ ] Name: `GEMINI_API_KEY`
- [ ] Value: ваш API ключ
- [ ] Нажать `Add secret`

### 3. Проверка прав доступа

- [ ] `Settings` → `Actions` → `General`
- [ ] Workflow permissions: `Read and write permissions` ✅
- [ ] Или настроить конкретные права в workflow

### 4. Тестирование

- [ ] Создать issue с текстом: `@gemini Привет! Это тест интеграции.`
- [ ] Проверить запуск workflow в `Actions`
- [ ] Ожидать ответ от AI в issue

## 🔧 Доступные workflow

### Основной (автоматический)

- **Файл**: `.github/workflows/gemini.yml`
- **Триггеры**: Issues, PR, комментарии с `@gemini`
- **Использует**: `google-gemini/gemini-cli-action@main`

### Резервный (ручной)

- **Файл**: `.github/workflows/gemini-backup.yml`  
- **Запуск**: Manual dispatch с номером issue
- **Использует**: Прямой API вызов Python

## 🎯 Команды для тестирования

```bash
# Создать тестовый issue
gh issue create --title "Тест Gemini AI" --body "@gemini Можешь проанализировать архитектуру проекта?"

# Проверить workflow
gh workflow list
gh run list --workflow="Gemini AI Assistant"

# Просмотр логов последнего запуска
gh run view --log
```

## 📊 Проверка интеграции

После настройки проверьте:

1. **Секреты настроены**: `Settings` → `Secrets` → `GEMINI_API_KEY` ✅
2. **Actions включены**: `Settings` → `Actions` → `Allow all actions` ✅
3. **Workflow работает**: Создайте issue с `@gemini` и проверьте `Actions`

## 🚨 Возможные проблемы

| Проблема | Решение |
|----------|---------|
| `GEMINI_API_KEY secret is not set` | Добавьте API ключ в repository secrets |
| Workflow не запускается | Проверьте права Actions в настройках |
| `Rate limit exceeded` | Подождите (лимиты: 60/мин, 1000/день) |
| Нет ответа от AI | Проверьте логи workflow в Actions |

## 🔗 Полезные ссылки

- 📖 [Полная документация](GEMINI.md)
- 🔑 [Google AI Studio](https://makersuite.google.com/)
- ⚙️ [GitHub Actions Docs](https://docs.github.com/en/actions)

---

**Следующий шаг**: Коммитьте изменения и создайте тестовый issue!
