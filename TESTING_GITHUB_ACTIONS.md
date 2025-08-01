# 🧪 Комплексная проверка GitHub Actions workflows

## 📋 Обзор задачи

Этот документ содержит детальный план тестирования всех GitHub Actions workflows после проведенного рефакторинга. Цель - убедиться в корректной работе всех компонентов и выявить возможные проблемы.

## 🎯 Цели тестирования

- Проверить функциональность всех 4 основных workflows
- Валидировать работу composite action
- Убедиться в корректности интеграций между компонентами
- Проверить обработку различных событий GitHub
- Валидировать безопасность и производительность

## 📊 Текущая структура workflows

### 1. **ai-assistants.yml** - 🤖 AI Ассистенты
- **Claude Assistant**: Основной AI помощник для issues/PR
- **Claude Code Review**: Специализированный code review
- **Gemini Assistant**: AI помощник на базе Google Gemini
- **Gemini CLI**: Продвинутые команды для Gemini

### 2. **issue-management.yml** - 📋 Управление Issues  
- **Auto-triage**: Автоматическая сортировка новых issues
- **Scheduled-triage**: Плановая сортировка по расписанию
- **Gemini-backup**: Резервный ответ Gemini

### 3. **pr-review.yml** - 🧐 PR Review
- **Gemini PR Review**: Детальный обзор pull requests

### 4. **validate-workflows.yml** - 🔍 Validate GitHub Actions
- **Validate Syntax**: YAML синтаксис
- **Validate Structure**: Структурная валидация
- **Test Composite Action**: Тестирование composite actions
- **Lint Workflows**: Проверка с actionlint
- **Security Check**: Анализ безопасности
- **Best Practices**: Проверка лучших практик

### 5. **setup-github-app** - Composite Action
- Централизованная настройка GitHub App токенов

## 🧪 Детальный план тестирования

### Фаза 1: Базовая функциональность

#### 1.1 Проверка синтаксиса и структуры

**Задачи:**
- [ ] Запустить `validate-workflows.yml` и убедиться, что все проверки проходят
- [ ] Проверить YAML синтаксис всех workflow файлов
- [ ] Валидировать структуру composite action
- [ ] Запустить actionlint для выявления потенциальных проблем
- [ ] Выполнить проверки безопасности

**Критерии успеха:**
- Все YAML файлы проходят валидацию
- Actionlint не выдает критических ошибок
- Composite action работает корректно
- Отсутствуют уязвимости безопасности

#### 1.2 Тестирование composite action

**Задачи:**
- [ ] Протестировать генерацию токена GitHub App (с реальными секретами)
- [ ] Протестировать fallback на GITHUB_TOKEN
- [ ] Проверить корректность output токена
- [ ] Валидировать обработку ошибок

**Тестовые сценарии:**
1. **Нормальный поток**: APP_ID и PRIVATE_KEY установлены
2. **Fallback поток**: APP_ID не установлен, используется GITHUB_TOKEN
3. **Ошибка**: Неверные учетные данные GitHub App

### Фаза 2: Функциональное тестирование AI ассистентов

#### 2.1 Claude Assistant

**Задачи:**
- [ ] Создать тестовое issue с упоминанием `@claude`
- [ ] Проверить отклик и качество ответа
- [ ] Тестировать различные типы запросов (код, рефакторинг, помощь)
- [ ] Валидировать работу с разными событиями (issues, comments, PR)

**Тестовые сценарии:**
1. **Issue comment**: `@claude помоги с исправлением бага`
2. **New issue**: Issue с `@claude` в теле
3. **PR comment**: `@claude проведи код-ревью`
4. **Pull request review**: Review с упоминанием `@claude`

#### 2.2 Claude Code Review

**Задачи:**
- [ ] Создать pull request и проверить автоматический code review
- [ ] Тестировать manual review через `@claude-review`
- [ ] Проверить качество обратной связи
- [ ] Валидировать sticky comment функциональность

**Тестовые сценарии:**
1. **Новый PR**: Автоматический запуск на opened PR
2. **Manual review**: Comment с `@claude-review`
3. **Специфические инструкции**: `@claude-review проверь безопасность`

#### 2.3 Gemini Assistant

**Задачи:**
- [ ] Проверить базовую функциональность Gemini
- [ ] Тестировать различные триггеры (`@gemini`, `@gemini-cli`)
- [ ] Валидировать интеграцию с Google Gemini API
- [ ] Проверить диагностику и error handling

**Тестовые сценарии:**
1. **Базовый вызов**: Issue comment с `@gemini`
2. **CLI команды**: `@gemini-cli` с продвинутыми запросами
3. **PR events**: Автоматический вызов на PR события
4. **Error scenarios**: Недоступность API, неверный ключ

#### 2.4 Gemini CLI

**Задачи:**
- [ ] Тестировать продвинутые команды
- [ ] Проверить авторизацию (только OWNER/MEMBER/COLLABORATOR)
- [ ] Валидировать работу с PR branches
- [ ] Тестировать Git операции (add, commit, push)

**Тестовые сценарии:**
1. **Authorized user**: Collaborator использует `@gemini-cli`
2. **Unauthorized user**: External contributor пытается использовать CLI
3. **Complex commands**: Рефакторинг кода, создание файлов
4. **Git operations**: Автоматические коммиты и push

### Фаза 3: Issue Management тестирование

#### 3.1 Auto-triage

**Задачи:**
- [ ] Создать новое issue и проверить автоматическую сортировку
- [ ] Тестировать применение соответствующих labels
- [ ] Проверить удаление `status/needs-triage` label
- [ ] Валидировать ручную сортировку через `/triage`

**Тестовые сценарии:**
1. **New issue**: Bug report issue
2. **Feature request**: Enhancement issue
3. **Manual triage**: Comment `/triage` на существующем issue
4. **Different types**: Security, documentation, question issues

#### 3.2 Scheduled Triage

**Задачи:**
- [ ] Протестировать workflow_dispatch с manual запуском
- [ ] Проверить поиск needing triage issues
- [ ] Валидировать массовую обработку issues
- [ ] Тестировать cron schedule (по возможности)

**Тестовые сценарии:**
1. **Manual dispatch**: Запуск через GitHub UI
2. **Multiple issues**: Несколько issues без labels
3. **Mixed states**: Issues с different priority levels

#### 3.3 Gemini Backup

**Задачи:**
- [ ] Тестировать резервный ответ через workflow_dispatch
- [ ] Проверить генерацию Python-based ответов
- [ ] Валидировать публикацию комментариев
- [ ] Проверить error handling

### Фаза 4: PR Review тестирование

#### 4.1 Gemini PR Review

**Задачи:**
- [ ] Создать PR и проверить автоматический review
- [ ] Тестировать manual review через `/review`
- [ ] Проверить качество feedback
- [ ] Валидировать работу с large PRs

**Тестовые сценарии:**
1. **Small PR**: Простые изменения в 1-2 файлах
2. **Large PR**: Комплексные изменения в multiple файлах
3. **Security-focused**: PR с потенциальными security issues
4. **Performance-focused**: PR с performance implications

### Фаза 5: Интеграционное тестирование

#### 5.1 Cross-workflow взаимодействия

**Задачи:**
- [ ] Тестировать concurrency controls
- [ ] Проверить shared resources (tokens, secrets)
- [ ] Валидировать event handling priorities
- [ ] Проверить performance под нагрузкой

#### 5.2 Error scenarios и resilience

**Задачи:**
- [ ] Тестировать API rate limits
- [ ] Проверить timeout scenarios
- [ ] Валидировать fallback mechanisms
- [ ] Тестировать partial failures

### Фаза 6: Performance и Security

#### 6.1 Performance тестирование

**Задачи:**
- [ ] Измерить время выполнения каждого workflow
- [ ] Проверить resource utilization
- [ ] Валидировать timeout settings
- [ ] Оптимизировать bottlenecks

#### 6.2 Security аудит

**Задачи:**
- [ ] Проверить permissions для каждого job
- [ ] Валидировать secrets handling
- [ ] Аудит third-party actions
- [ ] Проверить input validation

## 📝 Шаблоны для тестирования

### Тестовое Issue для Claude
```markdown
# Тест Claude Assistant

@claude помоги создать функцию для валидации email адресов в Python с использованием regex.

Требования:
- Функция должна возвращать True/False
- Поддержка основных email форматов
- Добавить unit tests
```

### Тестовое Issue для Gemini  
```markdown
# Тест Gemini Assistant

@gemini проанализируй структуру проекта и предложи улучшения архитектуры.

Фокус на:
- Организация модулей
- Зависимости между компонентами
- Потенциальные узкие места
```

### Тестовый PR для Code Review
```markdown
# Test PR для AI Code Review

Этот PR добавляет новый API endpoint для управления пользователями.

Изменения:
- Новый route `/api/users`
- Валидация входных данных
- Обработка ошибок
- Unit tests

@claude-review проверь безопасность и производительность
```

## 🎯 Критерии успешного тестирования

### Обязательные проверки
- [ ] Все workflows успешно запускаются
- [ ] AI ассистенты отвечают корректно и по существу
- [ ] Composite action работает во всех сценариях
- [ ] Issues автоматически сортируются
- [ ] PR получают quality reviews
- [ ] Отсутствуют security vulnerabilities
- [ ] Performance соответствует ожиданиям

### Дополнительные проверки
- [ ] Error handling работает корректно
- [ ] Fallback mechanisms функционируют
- [ ] Logs и diagnostics информативны
- [ ] Rate limits обрабатываются properly
- [ ] Concurrency controls работают эффективно

## 🚀 План выполнения

### Неделя 1: Базовое тестирование
- Фаза 1: Синтаксис и структура
- Фаза 2: AI ассистенты (базовые сценарии)

### Неделя 2: Углубленное тестирование  
- Фаза 3: Issue Management
- Фаза 4: PR Review
- Фаза 5: Интеграционное тестирование

### Неделя 3: Оптимизация и финализация
- Фаза 6: Performance и Security
- Исправление выявленных проблем
- Документирование результатов

## 📊 Отчетность

### Ежедневные отчеты
- Количество выполненных тестов
- Найденные проблемы и их severity
- Performance метрики
- Планы на следующий день

### Итоговый отчет
- Общее качество workflows после рефакторинга
- Список всех найденных и исправленных проблем
- Рекомендации по дальнейшим улучшениям
- Сравнение с состоянием до рефакторинга

## 🔧 Инструменты для тестирования

- **GitHub Actions**: Основная платформа
- **GitHub CLI**: Для manual testing и automation
- **actionlint**: Статический анализ workflows
- **PyYAML**: Валидация YAML синтаксиса
- **Custom scripts**: Автоматизация тестовых сценариев

## 📞 Контакты и поддержка

При обнаружении критических проблем:
1. Создать Issue с label `bug` и `priority/high`
2. Упомянуть @evgenygurin для notification
3. Приложить логи и steps to reproduce
4. Предложить temporary workaround если возможно

---
**Создано**: 2025-08-01  
**Версия**: 1.0  
**Автор**: Claude AI Assistant