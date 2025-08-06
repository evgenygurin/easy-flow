.PHONY: help install format lint test check security clean run dev

# Цвета для вывода
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m # No Color

help: ## Показать справку по командам
	@echo "$(BLUE)Доступные команды:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

check-setup: ## Проверить настройку проекта (Python 3.12 + uv)
	@echo "$(BLUE)Проверка настройки проекта...$(NC)"
	uv run python scripts/check_setup.py

install: ## Установить зависимости
	@echo "$(BLUE)Установка зависимостей...$(NC)"
	uv sync
	@echo "$(GREEN)✓ Зависимости установлены$(NC)"

install-dev: ## Установить зависимости для разработки
	@echo "$(BLUE)Установка зависимостей для разработки...$(NC)"
	uv sync --dev
	uv run pre-commit install
	@echo "$(GREEN)✓ Среда разработки настроена$(NC)"

format: ## Форматировать код
	@echo "$(BLUE)Форматирование кода...$(NC)"
	uv run ruff format app/ tests/
	@echo "$(GREEN)✓ Код отформатирован$(NC)"

lint: ## Проверить код линтерами
	@echo "$(BLUE)Проверка кода линтерами...$(NC)"
	uv run ruff check app/ tests/
	uv run ruff format --check app/ tests/
	uv run mypy app/ --config-file=pyproject.toml
	@echo "$(GREEN)✓ Линтинг завершен$(NC)"

security: ## Проверка безопасности
	@echo "$(BLUE)Проверка безопасности...$(NC)"
	@echo "$(YELLOW)Запуск Bandit...$(NC)"
	@if uv run bandit -r app/ --format json --output bandit-report.json; then \
		echo "$(GREEN)✓ Bandit: проблем не найдено$(NC)"; \
	else \
		echo "$(RED)⚠ Bandit: найдены проблемы безопасности, проверьте bandit-report.json$(NC)"; \
	fi
	@echo "$(YELLOW)Запуск Safety...$(NC)"
	@if uv run safety check --json --output safety-report.json; then \
		echo "$(GREEN)✓ Safety: уязвимостей не найдено$(NC)"; \
	else \
		echo "$(RED)⚠ Safety: найдены уязвимости, проверьте safety-report.json$(NC)"; \
	fi
	@echo "$(GREEN)✓ Проверка безопасности завершена$(NC)"
	@echo "$(YELLOW)Отчеты сохранены в bandit-report.json и safety-report.json$(NC)"

test: ## Запустить тесты
	@echo "$(BLUE)Запуск тестов...$(NC)"
	uv run pytest tests/ -v --tb=short
	@echo "$(GREEN)✓ Тесты пройдены$(NC)"

test-cov: ## Запустить тесты с покрытием
	@echo "$(BLUE)Запуск тестов с покрытием...$(NC)"
	uv run pytest tests/ --cov=app --cov-report=term-missing --cov-report=html
	@echo "$(GREEN)✓ Тесты с покрытием завершены$(NC)"
	@echo "$(YELLOW)HTML отчет доступен в htmlcov/index.html$(NC)"

check: format lint security test-cov ## Полная проверка (форматирование + линтинг + безопасность + тесты)
	@echo "$(GREEN)✓ Полная проверка завершена успешно!$(NC)"

pre-commit: ## Запустить pre-commit хуки
	@echo "$(BLUE)Запуск pre-commit хуков...$(NC)"
	uv run pre-commit run --all-files
	@echo "$(GREEN)✓ Pre-commit хуки выполнены$(NC)"

clean: ## Очистить временные файлы
	@echo "$(BLUE)Очистка временных файлов...$(NC)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -name "coverage.xml" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	find . -name "bandit-report.json" -delete 2>/dev/null || true
	find . -name "safety-report.json" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Временные файлы очищены$(NC)"

run: ## Запустить приложение
	@echo "$(BLUE)Запуск приложения...$(NC)"
	uv run uvicorn main:app --host 0.0.0.0 --port 8000

dev: ## Запустить приложение в режиме разработки
	@echo "$(BLUE)Запуск приложения в режиме разработки...$(NC)"
	uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

docker-build: ## Собрать Docker образ
	@echo "$(BLUE)Сборка Docker образа...$(NC)"
	docker build -t easy-flow .
	@echo "$(GREEN)✓ Docker образ собран$(NC)"

docker-run: ## Запустить в Docker
	@echo "$(BLUE)Запуск в Docker...$(NC)"
	docker run -p 8000:8000 easy-flow

docker-dev: ## Запустить development окружение с Docker Compose
	@echo "$(BLUE)Запуск development окружения...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Development окружение запущено$(NC)"

docker-stop: ## Остановить Docker Compose
	@echo "$(BLUE)Остановка Docker Compose...$(NC)"
	docker-compose down
	@echo "$(GREEN)✓ Docker Compose остановлен$(NC)"

migration-status: ## Показать статус миграции на Python 3.12 + uv
	@echo "$(GREEN)✅ Миграция на Python 3.12 + uv завершена!$(NC)"
	@echo ""
	@echo "$(BLUE)Основные изменения:$(NC)"
	@echo "  📦 $(YELLOW)pyproject.toml$(NC) - обновлен до Python 3.12"
	@echo "  🐍 $(YELLOW).python-version$(NC) - установлена версия 3.12"
	@echo "  🐳 $(YELLOW)Dockerfile$(NC) - использует Python 3.12 + uv"
	@echo "  🔧 $(YELLOW)Makefile$(NC) - все команды используют uv"
	@echo "  📚 $(YELLOW)README.md$(NC) - обновлена документация"
	@echo "  🎯 $(YELLOW)CLAUDE.md$(NC) - обновлены команды разработки"
	@echo ""
	@echo "$(BLUE)Следующие шаги:$(NC)"
	@echo "  1. $(GREEN)make check-setup$(NC)  - проверить настройку"
	@echo "  2. $(GREEN)make install-dev$(NC)  - установить зависимости"
	@echo "  3. $(GREEN)make dev$(NC)          - запустить разработку"

# Значение по умолчанию
.DEFAULT_GOAL := help