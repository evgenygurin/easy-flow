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

install: ## Установить зависимости
	@echo "$(BLUE)Установка зависимостей...$(NC)"
	pip install --upgrade pip
	pip install -r requirements.txt
	@echo "$(GREEN)✓ Зависимости установлены$(NC)"

install-dev: ## Установить зависимости для разработки
	@echo "$(BLUE)Установка зависимостей для разработки...$(NC)"
	pip install --upgrade pip
	pip install -r requirements.txt
	pre-commit install
	@echo "$(GREEN)✓ Среда разработки настроена$(NC)"

format: ## Форматировать код
	@echo "$(BLUE)Форматирование кода...$(NC)"
	ruff format app/ tests/
	@echo "$(GREEN)✓ Код отформатирован$(NC)"

lint: ## Проверить код линтерами
	@echo "$(BLUE)Проверка кода линтерами...$(NC)"
	ruff check app/ tests/
	ruff format --check app/ tests/
	mypy app/ --config-file=pyproject.toml
	@echo "$(GREEN)✓ Линтинг завершен$(NC)"

security: ## Проверка безопасности
	@echo "$(BLUE)Проверка безопасности...$(NC)"
	@echo "$(YELLOW)Запуск Bandit...$(NC)"
	@if bandit -r app/ --format json --output bandit-report.json; then \
		echo "$(GREEN)✓ Bandit: проблем не найдено$(NC)"; \
	else \
		echo "$(RED)⚠ Bandit: найдены проблемы безопасности, проверьте bandit-report.json$(NC)"; \
	fi
	@echo "$(YELLOW)Запуск Safety...$(NC)"
	@if safety check --json --output safety-report.json; then \
		echo "$(GREEN)✓ Safety: уязвимостей не найдено$(NC)"; \
	else \
		echo "$(RED)⚠ Safety: найдены уязвимости, проверьте safety-report.json$(NC)"; \
	fi
	@echo "$(GREEN)✓ Проверка безопасности завершена$(NC)"
	@echo "$(YELLOW)Отчеты сохранены в bandit-report.json и safety-report.json$(NC)"

test: ## Запустить тесты
	@echo "$(BLUE)Запуск тестов...$(NC)"
	pytest tests/ -v --tb=short
	@echo "$(GREEN)✓ Тесты пройдены$(NC)"

test-cov: ## Запустить тесты с покрытием
	@echo "$(BLUE)Запуск тестов с покрытием...$(NC)"
	pytest tests/ --cov=app --cov-report=term-missing --cov-report=html
	@echo "$(GREEN)✓ Тесты с покрытием завершены$(NC)"
	@echo "$(YELLOW)HTML отчет доступен в htmlcov/index.html$(NC)"

check: format lint security test-cov ## Полная проверка (форматирование + линтинг + безопасность + тесты)
	@echo "$(GREEN)✓ Полная проверка завершена успешно!$(NC)"

pre-commit: ## Запустить pre-commit хуки
	@echo "$(BLUE)Запуск pre-commit хуков...$(NC)"
	pre-commit run --all-files
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
	uvicorn main:app --host 0.0.0.0 --port 8000

dev: ## Запустить приложение в режиме разработки
	@echo "$(BLUE)Запуск приложения в режиме разработки...$(NC)"
	uvicorn main:app --host 0.0.0.0 --port 8000 --reload

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

# Значение по умолчанию
.DEFAULT_GOAL := help