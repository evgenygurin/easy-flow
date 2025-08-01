.PHONY: help install dev-install lint format type-check security test test-cov clean pre-commit-install pre-commit-run

# Цвета для красивого вывода
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

help: ## Показать помощь
	@echo "$(GREEN)Доступные команды:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Установить зависимости
	@echo "$(GREEN)Установка зависимостей...$(NC)"
	pip install -r requirements.txt

dev-install: install ## Установить зависимости для разработки
	@echo "$(GREEN)Установка pre-commit хуков...$(NC)"
	pre-commit install

lint: ## Проверить код с помощью ruff
	@echo "$(GREEN)Запуск линтера ruff...$(NC)"
	ruff check .

lint-fix: ## Проверить и исправить код с помощью ruff
	@echo "$(GREEN)Запуск линтера ruff с исправлениями...$(NC)"
	ruff check . --fix

format: ## Форматировать код с помощью ruff
	@echo "$(GREEN)Форматирование кода...$(NC)"
	ruff format .

format-check: ## Проверить форматирование кода
	@echo "$(GREEN)Проверка форматирования...$(NC)"
	ruff format --check .

type-check: ## Проверить типы с помощью mypy
	@echo "$(GREEN)Проверка типов...$(NC)"
	mypy app/ --config-file=pyproject.toml

security: ## Проверить безопасность с помощью bandit
	@echo "$(GREEN)Проверка безопасности...$(NC)"
	bandit -r app/ -f txt

security-json: ## Проверить безопасность и создать JSON отчет
	@echo "$(GREEN)Проверка безопасности (JSON отчет)...$(NC)"
	bandit -r app/ -f json -o bandit-report.json

test: ## Запустить тесты
	@echo "$(GREEN)Запуск тестов...$(NC)"
	pytest tests/ -v

test-cov: ## Запустить тесты с покрытием
	@echo "$(GREEN)Запуск тестов с покрытием...$(NC)"
	pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

pre-commit-install: ## Установить pre-commit хуки
	@echo "$(GREEN)Установка pre-commit хуков...$(NC)"
	pre-commit install

pre-commit-run: ## Запустить все pre-commit хуки
	@echo "$(GREEN)Запуск pre-commit хуков...$(NC)"
	pre-commit run --all-files

quality: lint-fix format type-check security ## Запустить все проверки качества кода

quality-check: lint format-check type-check security test ## Проверить качество кода без изменений

run: ## Запустить приложение
	@echo "$(GREEN)Запуск приложения...$(NC)"
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

run-prod: ## Запустить приложение в продакшен режиме
	@echo "$(GREEN)Запуск приложения (продакшен)...$(NC)"
	uvicorn main:app --host 0.0.0.0 --port 8000

docker-build: ## Собрать Docker образ
	@echo "$(GREEN)Сборка Docker образа...$(NC)"
	docker build -t easy-flow .

docker-run: ## Запустить Docker контейнер
	@echo "$(GREEN)Запуск Docker контейнера...$(NC)"
	docker run -p 8000:8000 easy-flow

docker-compose-up: ## Запустить через Docker Compose
	@echo "$(GREEN)Запуск через Docker Compose...$(NC)"
	docker-compose up -d

docker-compose-down: ## Остановить Docker Compose
	@echo "$(GREEN)Остановка Docker Compose...$(NC)"
	docker-compose down

clean: ## Очистить временные файлы
	@echo "$(GREEN)Очистка временных файлов...$(NC)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf htmlcov/
	rm -f .coverage
	rm -f bandit-report.json

ci: quality-check ## Запустить CI проверки локально