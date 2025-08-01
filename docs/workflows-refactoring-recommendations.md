# Рекомендации по рефакторингу GitHub Actions workflows

## 📋 Обзор текущего состояния

В проекте используется 8 workflow файлов для автоматизации процессов с AI-ассистентами (Gemini и Claude). Анализ показал несколько возможностей для оптимизации и улучшения.

## 🔍 Выявленные проблемы

### 1. Дублирование кода
- **Проблема**: Многие workflows содержат одинаковые шаги (клонирование репозитория, настройка токенов)
- **Затронутые файлы**: Все 8 workflow файлов
- **Решение**: Создать reusable workflows для общих операций

### 2. Неоптимальные условия запуска
- **Проблема**: Сложные и повторяющиеся условия `if` в джобах
- **Пример**: `gemini.yml` строки 15-24, `claude.yml` строки 15-21
- **Решение**: Упростить логику через composite actions

### 3. Отсутствие централизованной конфигурации
- **Проблема**: Настройки разбросаны по разным файлам
- **Решение**: Создать единый конфигурационный файл

### 4. Избыточность в permissions
- **Проблема**: Некоторые workflows запрашивают больше прав, чем необходимо
- **Решение**: Минимизировать права по принципу least privilege

### 5. Неконсистентные таймауты
- **Проблема**: Разные значения timeout-minutes (5, 10, 15 минут)
- **Решение**: Стандартизировать таймауты

## 🚀 Предлагаемые улучшения

### 1. Создание Reusable Workflows

**Файл: `.github/workflows/reusable-ai-setup.yml`**
```yaml
name: AI Setup Reusable Workflow

on:
  workflow_call:
    inputs:
      ai_provider:
        required: true
        type: string
      timeout_minutes:
        required: false
        type: number
        default: 10
    secrets:
      API_KEY:
        required: true
      GITHUB_TOKEN:
        required: true

jobs:
  setup:
    runs-on: ubuntu-latest
    timeout-minutes: ${{ inputs.timeout_minutes }}
    
    steps:
      - name: Генерация токена GitHub App
        id: generate_token
        if: ${{ vars.APP_ID }}
        uses: actions/create-github-app-token@v1
        with:
          app-id: ${{ vars.APP_ID }}
          private-key: ${{ secrets.PRIVATE_KEY }}

      - name: Клонирование репозитория
        uses: actions/checkout@v4
        with:
          token: ${{ steps.generate_token.outputs.token || secrets.GITHUB_TOKEN }}
          fetch-depth: 0
```

### 2. Composite Action для общих операций

**Файл: `.github/actions/setup-ai-environment/action.yml`**
```yaml
name: 'Setup AI Environment'
description: 'Настройка окружения для AI ассистентов'

inputs:
  ai_provider:
    description: 'AI провайдер (gemini/claude)'
    required: true
  api_key:
    description: 'API ключ'
    required: true

runs:
  using: 'composite'
  steps:
    - name: Проверка API ключа
      shell: bash
      run: |
        if [ -z "${{ inputs.api_key }}" ]; then
          echo "❌ API ключ не установлен для ${{ inputs.ai_provider }}"
          exit 1
        fi
        echo "✅ API ключ для ${{ inputs.ai_provider }} настроен"
```

### 3. Оптимизированный основной workflow

**Пример рефакторинга `gemini.yml`:**
```yaml
name: AI-ассистент Gemini

on:
  issues:
    types: [opened, edited]
  issue_comment:
    types: [created, edited]
  pull_request:
    types: [opened, synchronize, reopened]
  pull_request_review_comment:
    types: [created]

jobs:
  gemini:
    if: |
      github.repository == 'evgenygurin/easy-flow' && (
        contains(github.event.issue.body, '@gemini') ||
        contains(github.event.comment.body, '@gemini') ||
        github.event_name == 'pull_request'
      )
    
    uses: ./.github/workflows/reusable-ai-setup.yml
    with:
      ai_provider: 'gemini'
      timeout_minutes: 15
    secrets:
      API_KEY: ${{ secrets.GEMINI_API_KEY }}
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    
    steps:
      - name: Настройка AI окружения
        uses: ./.github/actions/setup-ai-environment
        with:
          ai_provider: 'gemini'
          api_key: ${{ secrets.GEMINI_API_KEY }}

      - name: Запуск AI-ассистента Gemini
        uses: google-gemini/gemini-cli-action@main
        with:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 4. Конфигурационный файл

**Файл: `.github/config/ai-workflows.yml`**
```yaml
# Общие настройки для AI workflows
defaults:
  timeout_minutes: 10
  permissions:
    contents: read
    pull-requests: write
    issues: write
  
gemini:
  timeout_minutes: 15
  permissions:
    contents: read
    pull-requests: write
    issues: write
    repository-projects: read

claude:
  timeout_minutes: 10
  permissions:
    contents: write
    pull-requests: write
    issues: write
    id-token: write
    actions: read

triage:
  timeout_minutes: 5
  schedule: '0 * * * *'  # каждый час
```

## 📊 Предполагаемые улучшения

### Уменьшение дублирования кода
- **Текущее состояние**: ~800 строк кода в workflows
- **После рефакторинга**: ~400-500 строк кода
- **Сокращение**: 40-50%

### Улучшение производительности
- Faster job startup за счет reusable workflows
- Параллельное выполнение независимых операций
- Оптимизированные условия запуска

### Повышение надежности
- Централизованная обработка ошибок
- Стандартизированные таймауты
- Минимальные права доступа

## 🔧 План внедрения

### Этап 1: Создание базовой инфраструктуры
1. Создать reusable workflow для общих операций
2. Создать composite actions для повторяющихся шагов
3. Добавить конфигурационный файл

### Этап 2: Рефакторинг существующих workflows
1. Обновить основные workflows (gemini.yml, claude.yml)
2. Оптимизировать PR review workflows
3. Упростить triage workflows

### Этап 3: Оптимизация и тестирование
1. Протестировать все сценарии
2. Оптимизировать производительность
3. Добавить мониторинг и логирование

## ⚠️ Важные замечания

### Безопасность
- Все секреты должны передаваться через secrets context
- Минимизировать права доступа
- Использовать официальные actions где возможно

### Совместимость
- Сохранить обратную совместимость с существующими триггерами
- Постепенный переход без нарушения работы

### Мониторинг
- Добавить логирование выполнения
- Настроить алерты для критичных ошибок
- Отслеживать производительность workflows

## 📝 Дополнительные рекомендации

### 1. Использование матричной стратегии
Для workflows, которые выполняют похожие операции для разных AI провайдеров:

```yaml
strategy:
  matrix:
    ai_provider: [gemini, claude]
    include:
      - ai_provider: gemini
        api_key: GEMINI_API_KEY
        action: google-gemini/gemini-cli-action@main
      - ai_provider: claude
        api_key: CLAUDE_CODE_OAUTH_TOKEN
        action: anthropics/claude-code-action@beta
```

### 2. Кэширование зависимостей
Добавить кэширование для Python зависимостей в резервном workflow:

```yaml
- name: Кэширование Python зависимостей
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

### 3. Условная логика
Использовать более читаемые условия:

```yaml
env:
  IS_GEMINI_TRIGGER: ${{ contains(github.event.comment.body, '@gemini') }}
  IS_CLAUDE_TRIGGER: ${{ contains(github.event.comment.body, '@claude') }}
  
jobs:
  ai-assistant:
    if: env.IS_GEMINI_TRIGGER || env.IS_CLAUDE_TRIGGER
```

---

*Этот документ содержит подробные рекомендации по рефакторингу GitHub Actions workflows для оптимизации производительности, уменьшения дублирования кода и повышения надежности.*