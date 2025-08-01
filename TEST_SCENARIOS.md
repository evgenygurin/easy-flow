# 🧪 Детальные тестовые сценарии для GitHub Actions

## 📋 Общие принципы тестирования

Каждый тестовый сценарий содержит:
- **Описание**: Что тестируется
- **Предварительные условия**: Настройки и состояние перед тестом
- **Шаги выполнения**: Детальная последовательность действий
- **Ожидаемый результат**: Что должно произойти
- **Критерии успеха**: Как определить успешность теста
- **Откат**: Как отменить изменения после теста

---

## 🤖 AI Assistants Workflow

### Сценарий 1.1: Claude Assistant - Issue Comment

**Описание**: Тестирование отклика Claude на упоминание в комментарии к issue

**Предварительные условия**:
- Репозиторий с активными workflows
- Секрет `CLAUDE_CODE_OAUTH_TOKEN` настроен
- GitHub App токены настроены

**Шаги выполнения**:
1. Открыть существующее issue или создать новое
2. Добавить комментарий: `@claude помоги создать функцию для проверки валидности email в Python`
3. Дождаться запуска workflow `ai-assistants.yml`
4. Проверить логи выполнения job `claude`
5. Дождаться ответа Claude в комментариях

**Ожидаемый результат**:
- Workflow запускается в течение 30 секунд
- Job `claude` выполняется успешно
- Claude публикует развернутый ответ с кодом функции
- Ответ включает unit tests и примеры использования

**Критерии успеха**:
- ✅ Workflow статус: SUCCESS
- ✅ Время выполнения < 15 минут
- ✅ Ответ Claude содержит функциональный код
- ✅ Код соответствует Python/FastAPI стандартам

### Сценарий 1.2: Claude Code Review - New PR

**Описание**: Автоматический код-ревью от Claude при создании PR

**Предварительные условия**:
- Готовый PR с изменениями в Python коде
- Секреты Claude настроены

**Шаги выполнения**:
1. Создать новый pull request с изменениями
2. Проверить автоматический запуск job `claude-review`
3. Дождаться завершения анализа
4. Проверить комментарии в PR

**Ожидаемый результат**:
- Автоматический запуск в течение 1 минуты после создания PR
- Claude публикует структурированный код-ревью
- Ревью включает анализ безопасности, производительности, стиля

**Критерии успеха**:
- ✅ Job завершается за < 10 минут
- ✅ Sticky comment создается в PR
- ✅ Ревью следует заданному формату
- ✅ Выявляются реальные проблемы кода

### Сценарий 1.3: Gemini Assistant - PR Events

**Описание**: Тестирование Gemini на различных PR событиях

**Предварительные условия**:
- Секрет `GEMINI_API_KEY` настроен
- Открытый PR для тестирования

**Шаги выполнения**:
1. Создать PR comment с `@gemini проанализируй производительность изменений`
2. Добавить PR review comment с `@gemini`
3. Submit PR review с упоминанием `@gemini`
4. Проверить отклики на каждое действие

**Ожидаемый результат**:
- Job `gemini` запускается для каждого события
- Gemini отвечает контекстно на каждый запрос
- Диагностическая информация записывается в логи

**Критерии успеха**:
- ✅ Все три триггера работают
- ✅ Ответы релевантны запросам
- ✅ Diagnostic step показывает корректную информацию
- ✅ Обработка ошибок работает при недоступности API

### Сценарий 1.4: Gemini CLI - Advanced Commands

**Описание**: Тестирование продвинутых CLI команд Gemini

**Предварительные условия**:
- Пользователь с правами COLLABORATOR или выше
- Активный PR для работы

**Шаги выполнения**:
1. В PR comment написать: `@gemini-cli создай unit test для функции calculate_total в файле app/services/integration_service.py`
2. Проверить авторизацию пользователя
3. Дождаться клонирования правильной ветки PR
4. Проверить выполнение команд через shell
5. Проверить Git операции (add, commit, push)

**Ожидаемый результат**:
- Авторизация проходит успешно
- PR branch клонируется корректно
- Создается файл с unit tests
- Изменения коммитятся и пушатся в PR branch

**Критерии успеха**:
- ✅ Только авторизованные пользователи могут запускать
- ✅ Корректная работа с PR branches
- ✅ Git операции выполняются успешно
- ✅ Результат публикуется в PR comment

---

## 📋 Issue Management Workflow

### Сценарий 2.1: Auto-triage - New Issue

**Описание**: Автоматическая сортировка нового issue

**Предварительные условия**:
- Настроены labels в репозитории
- Gemini API key активен

**Шаги выполнения**:
1. Создать новое issue:
   ```markdown
   # Bug: API returns 500 error
   
   ## Description
   When calling /api/users endpoint with invalid parameters, 
   the API returns 500 instead of 400 error.
   
   ## Steps to reproduce
   1. Send POST request to /api/users
   2. Include invalid email format
   3. Observe 500 response
   
   ## Expected behavior
   Should return 400 Bad Request with validation errors
   ```
2. Дождаться запуска `auto-triage` job
3. Проверить применение labels
4. Убедиться в удалении `status/needs-triage` label

**Ожидаемый результат**:
- Issue получает labels: `kind/bug`, `area/api`, `priority/medium`
- Label `status/needs-triage` удаляется
- Процесс завершается за < 5 минут

**Критерии успеха**:
- ✅ Labels применяются автоматически
- ✅ Labels соответствуют содержанию issue
- ✅ Triage label удаляется
- ✅ Job завершается успешно

### Сценарий 2.2: Manual Triage Command

**Описание**: Ручная сортировкаissue через команду

**Предварительные условия**:
- Issue без labels или с неправильными labels
- Пользователь с правами COLLABORATOR+

**Шаги выполнения**:
1. В issue comment написать: `@gemini-cli /triage`
2. Проверить авторизацию
3. Дождаться анализа issue
4. Проверить обновление labels

**Ожидаемый результат**:
- Gemini анализирует содержимое issue
- Применяются релевантные labels
- Предыдущие неправильные labels корректируются

**Критерии успеха**:
- ✅ Только авторизованные пользователи могут запускать
- ✅ Labels обновляются корректно
- ✅ Система обрабатывает edge cases

### Сценарий 2.3: Scheduled Triage

**Описание**: Массовая сортировка issues по расписанию

**Предварительные условия**:
- Несколько issues без labels
- Issues с label `status/needs-triage`

**Шаги выполнения**:
1. Создать 3-5 issues без labels различных типов
2. Запустить workflow manually через `workflow_dispatch`
3. Проверить поиск issues для сортировки
4. Дождаться массовой обработки
5. Проверить results для каждого issue

**Ожидаемый результат**:
- Система находит все issues requiring triage
- Каждый issue обрабатывается индивидуально
- Labels применяются согласно содержанию

**Критерии успеха**:
- ✅ Находятся все подходящие issues
- ✅ Batch processing работает корректно
- ✅ Каждый issue получает appropriate labels
- ✅ Performance приемлемая для большого количества issues

### Сценарий 2.4: Gemini Backup Response

**Описание**: Резервный ответ Gemini через workflow_dispatch

**Предварительные условия**:
- Issue требующий AI ответа
- Python environment настроен

**Шаги выполнения**:
1. Выбрать issue для резервного ответа
2. Запустить workflow с параметрами:
   - `issue_number`: номер issue
   - `action`: `backup-response`
3. Проверить генерацию ответа через Python script
4. Проверить публикацию комментария

**Ожидаемый результат**:
- Python script успешно генерирует AI ответ
- Ответ публикуется как комментарий к issue
- Формат комментария соответствует шаблону

**Критерии успеха**:
- ✅ Python integration работает
- ✅ Gemini API отвечает корректно
- ✅ Комментарий публикуется успешно
- ✅ Error handling работает при API failures

---

## 🧐 PR Review Workflow

### Сценарий 3.1: Automatic PR Review

**Описание**: Автоматический обзор PR при открытии

**Предварительные условия**:
- PR с существенными изменениями кода
- Gemini API настроен

**Шаги выполнения**:
1. Создать PR с изменениями в multiple файлах:
   - Добавить новый API endpoint
   - Изменить existing function  
   - Добавить новый test file
2. Проверить автоматический запуск PR review
3. Дождаться анализа всех changed files
4. Проверить качество feedback

**Ожидаемый результат**:
- Review запускается автоматически при создании PR
- Анализируются все измененные файлы
- Feedback структурирован по приоритетам
- Включены конкретные рекомендации

**Критерии успеха**:
- ✅ Автоматический trigger работает
- ✅ Все файлы анализируются
- ✅ Feedback полезный и actionable
- ✅ Формат соответствует template

### Сценарий 3.2: Manual PR Review с инструкциями

**Описание**: Ручной обзор с специфическими инструкциями

**Предварительные условия**:
- Существующий PR
- Specific areas of concern

**Шаги выполнения**:
1. В PR comment написать: `@gemini-cli /review проверь безопасность аутентификации`
2. Проверить parsing дополнительных инструкций
3. Дождаться targeted анализа
4. Проверить focus на указанных областях

**Ожидаемый результат**:
- Дополнительные инструкции правильно парсятся
- Review фокусируется на безопасности
- Глубокий analysis authentication flows
- Specific recommendations по улучшению

**Критерии успеха**:
- ✅ Additional instructions обрабатываются
- ✅ Focus area получает больше внимания
- ✅ Specialized knowledge применяется
- ✅ Recommendations релевантны запросу

### Сценарий 3.3: Large PR Review

**Описание**: Обзор крупного PR с множественными изменениями

**Предварительные условия**:
- PR с 10+ измененными файлами
- Различные типы изменений (code, tests, docs)

**Шаги выполнения**:
1. Создать или выбрать large PR
2. Запустить review workflow
3. Мониторить performance и memory usage
4. Проверить completeness анализа
5. Validate timeout handling

**Ожидаемый результат**:
- System handles large PRs без failures
- Все файлы анализируются within timeout
- Performance остается приемлемой
- Review comprehensive но не overwhelming

**Критерии успеха**:
- ✅ No timeout failures
- ✅ All significant changes analyzed
- ✅ Response time < 15 minutes
- ✅ Memory usage within limits

---

## 🔍 Validation Workflow

### Сценарий 4.1: YAML Syntax Validation

**Описание**: Проверка синтаксиса всех YAML файлов

**Предварительные условия**:
- Workflows и actions в актуальном состоянии
- Python environment доступен

**Шаги выполнения**:
1. Внести intentional syntax error в workflow file
2. Запустить `validate-workflows.yml`
3. Проверить detection ошибки
4. Исправить ошибку
5. Повторить validation

**Ожидаемый результат**:
- Syntax errors детектируются корректно
- Error messages информативны
- Fixed files проходят validation
- Process завершается быстро

**Критерии успеха**:
- ✅ Errors обнаруживаются точно
- ✅ No false positives
- ✅ Clear error messages
- ✅ Fast execution (< 5 minutes)

### Сценарий 4.2: Structural Validation

**Описание**: Проверка структуры workflows через validate_actions.py

**Предварительные условия**:
- Script validate_actions.py существует
- Все workflows следуют expected structure

**Шаги выполнения**:
1. Запустить structural validation
2. Проверить analysis results
3. Проверить compliance с best practices
4. Validate suggestions для improvements

**Ожидаемый результат**:
- Структура workflows анализируется полностью
- Best practices violations выявляются
- Рекомендации по улучшению предоставляются
- No critical structural issues

**Критерии успеха**:
- ✅ Comprehensive analysis проводится
- ✅ Recommendations являются actionable
- ✅ No false violations reported
- ✅ Clear documentation выдается

### Сценарий 4.3: Composite Action Testing

**Описание**: Тестирование setup-github-app composite action

**Предварительные условия**:
- Composite action в .github/actions/setup-github-app/
- Test environment с ограниченными permissions

**Шаги выполнения**:
1. Тест с empty APP_ID (fallback scenario)
2. Тест с invalid credentials
3. Тест с valid credentials
4. Проверить outputs в каждом случае
5. Validate error messages

**Ожидаемый результат**:
- Fallback к GITHUB_TOKEN работает
- Error scenarios обрабатываются gracefully
- Valid credentials генерируют рабочий token
- Outputs consistent и reliable

**Критерии успеха**:
- ✅ All scenarios test successfully
- ✅ Fallback mechanism работает
- ✅ Error handling robust
- ✅ Token output format consistent

### Сценарий 4.4: Security Analysis

**Описание**: Автоматический security audit workflows

**Предварительные условия**:
- Security check script active
- Workflows содержат потенциальные risks

**Шаги выполнения**:
1. Добавить hardcoded token в workflow (для теста)
2. Запустить security check
3. Проверить detection
4. Добавить overprivileged permissions
5. Validate permission analysis
6. Test shell injection detection

**Ожидаемый результат**:
- Hardcoded tokens детектируются
- Excessive permissions выявляются
- Shell injection vectors находятся
- Clear remediation guidance предоставляется

**Критерии успеха**:
- ✅ Security issues найдены точно
- ✅ No false positives в normal code
- ✅ Clear security guidance
- ✅ Fast security scanning

### Сценарий 4.5: Best Practices Check

**Описание**: Проверка соответствия GitHub Actions best practices

**Предварительные условия**:
- Workflows в production state
- Best practices checker active

**Шаги выполнения**:
1. Проверить pinned action versions
2. Validate timeout settings
3. Check concurrency controls
4. Analyze resource usage patterns
5. Review permission configurations

**Ожидаемый результат**:
- Unpinned actions выявляются
- Missing timeouts обнаруживаются
- Concurrency gaps найдены
- Comprehensive best practices report

**Критерии успеха**:
- ✅ All best practices categories checked
- ✅ Actionable recommendations
- ✅ Clear priority levels
- ✅ No subjective false positives

---

## 🚀 Integration Testing Scenarios

### Сценарий 5.1: Concurrent Workflow Execution

**Описание**: Тестирование multiple workflows running simultaneously

**Предварительные условия**:
- Multiple active PRs and issues
- Concurrency controls настроены

**Шаги выполнения**:
1. Создать simultaneous events:
   - New PR (triggers ai-assistants, pr-review)
   - Issue comment с @claude
   - Issue comment с @gemini
   - Manual workflow dispatch
2. Мониторить resource utilization
3. Проверить concurrency group behavior
4. Validate no race conditions

**Ожидаемый результат**:
- Workflows выполняются без conflicts
- Concurrency limits соблюдаются
- Resource utilization остается healthy
- All outputs корректны

**Критерии успеха**:
- ✅ No workflow failures due to concurrency
- ✅ Resource limits respected
- ✅ All expected outputs generated
- ✅ Performance degradation минимальна

### Сценарий 5.2: Error Recovery Testing

**Описание**: Тестирование обработки ошибок и recovery mechanisms

**Предварительные условия**:
- Workflows с fallback mechanisms
- Temporary service disruptions возможны

**Шаги выполнения**:
1. Simulate API rate limits (GitHub API)
2. Test with invalid secrets
3. Trigger timeout scenarios
4. Test network connectivity issues
5. Validate error messaging
6. Check recovery behavior

**Ожидаемый результат**:
- Graceful degradation при API issues
- Clear error messages для users
- Automatic retries где appropriate
- Fallback mechanisms активируются

**Критерии успеха**:
- ✅ No silent failures
- ✅ User-friendly error messages
- ✅ Appropriate retry behavior
- ✅ System remains stable под stress

### Сценарий 5.3: End-to-End User Journey

**Описание**: Полный user journey через различные workflows

**Предварительные условия**:
- Fresh test repository state
- All integrations active

**Шаги выполнения**:
1. Создать new issue с @claude
2. Дождаться Claude response
3. Создать PR addressing issue
4. Получить automatic code review
5. Request manual Gemini review
6. Trigger triage на related issues
7. Complete PR merge cycle

**Ожидаемый результат**:
- Seamless experience across workflows
- Consistent AI assistance quality
- All integrations work together
- User feedback положительный

**Критерии успеха**:
- ✅ Complete journey без manual intervention
- ✅ Consistent experience quality
- ✅ All AI responses helpful
- ✅ Performance meets expectations

---

## 📊 Performance Testing

### Сценарий 6.1: Load Testing

**Описание**: Тестирование under high load conditions

**Предварительные условия**:
- Ability to generate multiple events
- Monitoring tools настроены

**Шаги выполнения**:
1. Генерировать 10+ simultaneous events
2. Monitor workflow execution times
3. Check for failures or timeouts
4. Analyze resource consumption
5. Validate output quality under load

**Ожидаемый результат**:
- System handles increased load gracefully
- Response times remain acceptable
- Quality не деградирует significantly
- No system failures

**Критерии успеха**:
- ✅ <10% failure rate under load
- ✅ Response times < 2x normal
- ✅ Quality standards maintained
- ✅ Resource usage within limits

### Сценарий 6.2: Memory и Resource Testing

**Описание**: Анализ memory usage и resource consumption

**Предварительные условия**:
- Monitoring capabilities
- Large files для processing

**Шаги выполнения**:
1. Process large PRs (100+ files)
2. Handle complex AI requests
3. Monitor memory usage patterns
4. Check for memory leaks
5. Validate cleanup processes

**Ожидаемый результат**:
- Memory usage remains within bounds
- No memory leaks detected
- Cleanup processes work correctly
- Performance scales reasonably

**Критерии успеха**:
- ✅ Memory usage < GitHub runner limits
- ✅ No persistent memory growth
- ✅ Cleanup completes successfully
- ✅ Performance degrades linearly

---

## 🎯 Success Criteria Summary

### Critical Success Metrics
- **Availability**: >95% workflow success rate
- **Performance**: <15 min average execution time
- **Quality**: >80% positive user feedback on AI responses
- **Security**: 0 critical security violations
- **Reliability**: <5% failure rate under normal load

### Quality Gates
- All syntax validations pass
- No security vulnerabilities
- Performance within acceptable ranges
- User experience meets expectations
- Error handling works correctly

### Acceptance Criteria
- All test scenarios pass successfully
- Documentation is complete и accurate
- Rollback procedures are verified
- Monitoring и alerting работают
- Team training завершен

---
**Последнее обновление**: 2025-08-01  
**Версия**: 1.0  
**Статус**: Ready for Execution