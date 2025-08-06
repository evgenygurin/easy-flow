"""Базовые классы для адаптеров интеграций."""
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.models.ecommerce import Customer, Order, Product


logger = structlog.get_logger()


class AdapterError(Exception):
    """Базовое исключение для адаптеров интеграций."""

    def __init__(self, message: str, platform: str, error_code: str | None = None):
        super().__init__(message)
        self.platform = platform
        self.error_code = error_code


class RateLimitError(AdapterError):
    """Исключение при превышении лимита запросов."""

    def __init__(self, message: str, platform: str, retry_after: int | None = None):
        super().__init__(message, platform, "RATE_LIMIT")
        self.retry_after = retry_after


class AuthenticationError(AdapterError):
    """Исключение при ошибках аутентификации."""

    def __init__(self, message: str, platform: str):
        super().__init__(message, platform, "AUTH_ERROR")


class SyncResult(BaseModel):
    """Результат синхронизации данных."""

    success: bool = Field(..., description="Успешность синхронизации")
    records_synced: int = Field(default=0, description="Количество синхронизированных записей")
    sync_type: str = Field(..., description="Тип синхронизации")
    timestamp: datetime = Field(default_factory=datetime.now, description="Время синхронизации")
    errors: list[str] = Field(default_factory=list, description="Список ошибок")


class PlatformAdapter(ABC):
    """Базовый адаптер для интеграции с внешними платформами."""

    def __init__(self, platform_name: str, credentials: dict[str, str], config: dict[str, Any] | None = None):
        self.platform_name = platform_name
        self.credentials = credentials
        self.config = config or {}
        self.logger = structlog.get_logger().bind(platform=platform_name)

    @abstractmethod
    async def authenticate(self) -> bool:
        """Проверить подключение и аутентификацию."""

    @abstractmethod
    async def sync_orders(self, since: datetime | None = None) -> SyncResult:
        """Синхронизация заказов."""

    @abstractmethod
    async def sync_products(self, since: datetime | None = None) -> SyncResult:
        """Синхронизация товаров."""

    @abstractmethod
    async def sync_customers(self, since: datetime | None = None) -> SyncResult:
        """Синхронизация клиентов."""

    @abstractmethod
    async def handle_webhook(self, event_type: str, payload: dict[str, Any]) -> str:
        """Обработка входящего webhook."""

    @abstractmethod
    async def get_order_status(self, order_id: str) -> str:
        """Получить статус заказа."""

    @abstractmethod
    async def update_order_status(self, order_id: str, status: str) -> bool:
        """Обновить статус заказа."""

    async def validate_connection(self) -> bool:
        """Проверить подключение к платформе."""
        try:
            return await self.authenticate()
        except Exception as e:
            self.logger.error("Ошибка проверки подключения", error=str(e))
            return False

    def _generate_message_id(self) -> str:
        """Генерировать уникальный ID сообщения."""
        return str(uuid.uuid4())

    def _log_api_call(self, method: str, endpoint: str, response_status: int):
        """Логирование API вызовов."""
        self.logger.info(
            "API вызов",
            method=method,
            endpoint=endpoint,
            status=response_status
        )


class OrderAdapter(ABC):
    """Адаптер для работы с заказами."""

    @abstractmethod
    async def create_order(self, order: Order) -> str:
        """Создать заказ в внешней системе."""

    @abstractmethod
    async def update_order(self, order_id: str, order: Order) -> bool:
        """Обновить заказ в внешней системе."""

    @abstractmethod
    async def cancel_order(self, order_id: str, reason: str) -> bool:
        """Отменить заказ."""


class ProductAdapter(ABC):
    """Адаптер для работы с товарами."""

    @abstractmethod
    async def get_product(self, product_id: str) -> Product | None:
        """Получить информацию о товаре."""

    @abstractmethod
    async def update_product(self, product_id: str, product: Product) -> bool:
        """Обновить информацию о товаре."""

    @abstractmethod
    async def update_stock(self, product_id: str, quantity: int) -> bool:
        """Обновить остатки товара."""


class CustomerAdapter(ABC):
    """Адаптер для работы с клиентами."""

    @abstractmethod
    async def get_customer(self, customer_id: str) -> Customer | None:
        """Получить информацию о клиенте."""

    @abstractmethod
    async def create_customer(self, customer: Customer) -> str:
        """Создать клиента в внешней системе."""

    @abstractmethod
    async def update_customer(self, customer_id: str, customer: Customer) -> bool:
        """Обновить информацию о клиенте."""


class IntegrationHealthCheck:
    """Проверка здоровья интеграций."""

    def __init__(self, adapter: PlatformAdapter):
        self.adapter = adapter

    async def check_health(self) -> dict[str, Any]:
        """Проверить статус интеграции."""
        try:
            start_time = datetime.now()
            
            # Проверка аутентификации
            auth_ok = await self.adapter.authenticate()
            
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds() * 1000

            return {
                "platform": self.adapter.platform_name,
                "status": "healthy" if auth_ok else "unhealthy",
                "response_time_ms": response_time,
                "last_check": end_time.isoformat(),
                "authentication": "ok" if auth_ok else "failed"
            }
        except Exception as e:
            return {
                "platform": self.adapter.platform_name,
                "status": "error",
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }


class RateLimiter:
    """Простой rate limiter для API запросов."""

    def __init__(self, requests_per_hour: int = 1000):
        self.requests_per_hour = requests_per_hour
        self.requests_made = 0
        self.window_start = datetime.now()

    async def can_make_request(self) -> bool:
        """Проверить, можно ли делать запрос."""
        current_time = datetime.now()
        
        # Сброс окна каждый час
        if (current_time - self.window_start).seconds >= 3600:
            self.requests_made = 0
            self.window_start = current_time

        return self.requests_made < self.requests_per_hour

    async def record_request(self):
        """Записать совершенный запрос."""
        self.requests_made += 1

    def get_requests_left(self) -> int:
        """Получить количество оставшихся запросов."""
        return max(0, self.requests_per_hour - self.requests_made)